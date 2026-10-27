"""
rules.py - Turns raw detections into traffic violations. Pure Python, no AI, easy to test.

The model only finds boxes: motorcyclist, helmet, no_helmet, plate.
This file decides what they MEAN:

  1. Each helmet / no_helmet box (a "head") is given to the motorcyclist box it sits in.
  2. Each plate is given to the motorcyclist box it sits in.
  3. For every motorcyclist:
       - any head without a helmet       -> NO_HELMET violation
       - 3 or more heads on one bike      -> TRIPLE_RIDING violation
       - no heads found at all            -> "unclear" (never a violation; we do not guess)

Used by: app/services/analyzer.py, app/services/tracker.py
"""
from app import config


def area(box):
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def intersection(a, b):
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def iou(a, b):
    inter = intersection(a, b)
    union = area(a) + area(b) - inter
    return inter / union if union > 0 else 0.0


def inside_ratio(small, big):
    """How much of `small` is inside `big` (0..1)."""
    a = area(small)
    return intersection(small, big) / a if a > 0 else 0.0


def _best_owner(box, bikes, min_inside, prefer):
    """
    Pick the motorcyclist that owns this head/plate.
    prefer="top": heads belong to the bike whose upper part they are in.
    prefer="bottom": plates belong to the bike whose lower part they are in.
    """
    best, best_score = None, 0.0
    for i, bike in enumerate(bikes):
        overlap = inside_ratio(box, bike["box"])
        if overlap < min_inside:
            continue
        x1, y1, x2, y2 = bike["box"]
        centre_y = (box[1] + box[3]) / 2
        relative_y = (centre_y - y1) / max(1.0, y2 - y1)          # 0 = top of bike box, 1 = bottom
        position = (1 - relative_y) if prefer == "top" else relative_y
        score = overlap + 0.3 * position
        if score > best_score:
            best, best_score = i, score
    return best


def has_orphan_heads(detections):
    """True when a helmet/no_helmet head is not inside any motorcyclist box."""
    bikes = [d["box"] for d in detections if d["role"] == "motorcyclist"]
    heads = [d["box"] for d in detections if d["role"] in ("helmet", "no_helmet")]
    return any(all(inside_ratio(h, b) < 0.5 for b in bikes) for h in heads)


def bikes_from_coco(coco_detections, existing, min_conf=0.3):
    """
    Backup: build motorcyclist boxes from a COCO model's 'motorcycle' + 'person' boxes.
    rider box = the motorcycle box joined with every person sitting on it
    (person's centre above the bike's centre line and horizontally over the bike).
    Bikes that the main model already found are skipped.
    """
    motorcycles = [d for d in coco_detections if d["label"] == "motorcycle" and d["conf"] >= min_conf]
    people = [d for d in coco_detections if d["label"] == "person" and d["conf"] >= min_conf]
    found = []
    for m in motorcycles:
        x1, y1, x2, y2 = m["box"]
        box = list(m["box"])
        for p in people:
            px = (p["box"][0] + p["box"][2]) / 2
            on_bike = x1 <= px <= x2 and p["box"][3] > y1 and inside_ratio(p["box"], m["box"]) >= 0.15
            if on_bike:
                box = [min(box[0], p["box"][0]), min(box[1], p["box"][1]),
                       max(box[2], p["box"][2]), max(box[3], p["box"][3])]
        if any(iou(box, e["box"]) > 0.3 for e in existing):
            continue
        found.append({"role": "motorcyclist", "label": "motorcycle+person", "conf": m["conf"],
                      "box": [round(v, 1) for v in box], "source": "backup"})
    return found


def group_by_motorcyclist(detections):
    """
    Returns one dict per motorcyclist:
      {"box", "conf", "heads": [det...], "plates": [det...]}
    """
    bikes = [{"box": d["box"], "conf": d["conf"], "heads": [], "plates": []}
             for d in detections if d["role"] == "motorcyclist"]
    for d in detections:
        if d["role"] in ("helmet", "no_helmet"):
            owner = _best_owner(d["box"], bikes, min_inside=0.5, prefer="top")
            if owner is not None:
                bikes[owner]["heads"].append(d)
        elif d["role"] == "plate":
            owner = _best_owner(d["box"], bikes, min_inside=0.6, prefer="bottom")
            if owner is not None:
                bikes[owner]["plates"].append(d)
    for bike in bikes:
        bike["heads"] = _remove_duplicate_heads(bike["heads"])
        bike["plates"].sort(key=lambda p: p["conf"], reverse=True)
    return bikes


def _remove_duplicate_heads(heads):
    """The model sometimes puts BOTH a helmet and a no_helmet box on one head: keep the surer one."""
    kept = []
    for head in sorted(heads, key=lambda h: h["conf"], reverse=True):
        if all(iou(head["box"], k["box"]) < 0.5 for k in kept):
            kept.append(head)
    return kept


def judge(bike):
    """
    Decide the violations for ONE motorcyclist.
    Returns {"riders", "no_helmet_count", "status", "violations": [{"type", "confidence"}]}
    """
    heads = bike["heads"]
    no_helmet = [h for h in heads if h["role"] == "no_helmet"]
    result = {"riders": len(heads), "no_helmet_count": len(no_helmet), "violations": []}

    if not heads:
        result["status"] = "unclear"
        return result

    if no_helmet:
        result["violations"].append({
            "type": "NO_HELMET",
            "confidence": round(max(h["conf"] for h in no_helmet), 3),
        })
    if len(heads) >= config.TRIPLE_RIDING_MIN:
        result["violations"].append({
            "type": "TRIPLE_RIDING",
            "confidence": round(min(sorted(h["conf"] for h in heads)[-config.TRIPLE_RIDING_MIN:]), 3),
        })
    result["status"] = "violation" if result["violations"] else "ok"
    return result


def analyse_detections(detections):
    """Detections of ONE frame -> list of motorcyclists with their verdicts."""
    bikes = group_by_motorcyclist(detections)
    for bike in bikes:
        bike.update(judge(bike))
    return bikes
