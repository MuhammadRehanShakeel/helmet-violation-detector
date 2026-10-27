"""
eval_plates.py - How well do we read Pakistani number plates?

Compares two things on the synthetic plates (evaluation/data/synthetic_plates_test):
  * raw OCR             - what RapidOCR reads, only upper-cased and spaces removed
  * OCR + our clean-up  - after normalise_plate() (province words, year, 0/O, 1/I ... fixed)

Metrics
  * exact match - the whole plate is right (what matters for a challan)
  * CER         - character error rate (how many characters are wrong, lower is better)
  * accepted    - plates the system marked "valid"; precision = of those, how many were right
                  (a wrong plate on a challan is worse than "unreadable, officer please type it")

Run:  backend\\venv\\Scripts\\python.exe evaluation\\eval_plates.py
"""
import json
import os
import sys
import time
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))
os.environ.setdefault("DB_SERVER", "eval")
os.environ.setdefault("JWT_SECRET", "eval-only-secret")

import cv2  # noqa: E402

from app import config  # noqa: E402
from app.services.plates import PlateReader, compact, normalise_plate  # noqa: E402

SPLIT = sys.argv[1] if len(sys.argv) > 1 else "test"       # "dev" while tuning, "test" for the report
DATA = os.path.join(HERE, "data", f"synthetic_plates_{SPLIT}")
LEVELS = {0: "close & clear", 1: "medium distance", 2: "far, dark, noisy", 3: "very far, low quality"}


def cer(predicted: str, truth: str) -> float:
    """Levenshtein distance / length of the truth."""
    a, b = predicted, truth
    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, row[0] = row[0], i
        for j, cb in enumerate(b, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (ca != cb))
    return row[len(b)] / max(1, len(b))


def main():
    if not os.path.exists(os.path.join(DATA, "labels.json")):
        sys.path.insert(0, HERE)
        import make_synthetic_plates
        make_synthetic_plates.main(SPLIT)
    labels = json.load(open(os.path.join(DATA, "labels.json")))
    reader = PlateReader()
    stats = defaultdict(lambda: defaultdict(float))
    examples = []
    started = time.time()

    for item in labels:
        image = cv2.imread(os.path.join(DATA, item["file"]))
        raw, conf = reader.ocr_text(image)
        cleaned = normalise_plate(raw)
        truth = compact(item["plate"])
        raw_compact = compact(raw)
        ours = compact(cleaned["plate"] or "")
        accepted = cleaned["valid"] and conf >= config.PLATE_MIN_CONFIDENCE

        for key in ("all", f"level {item['level']}", item["style"]):
            s = stats[key]
            s["n"] += 1
            s["raw_exact"] += raw_compact == truth
            s["ours_exact"] += ours == truth
            s["raw_cer"] += cer(raw_compact, truth)
            s["ours_cer"] += cer(ours, truth)
            s["accepted"] += accepted
            s["accepted_right"] += accepted and ours == truth
        if raw_compact != truth and ours == truth and len(examples) < 12:
            examples.append({"truth": item["plate"], "raw_ocr": raw, "after_cleanup": cleaned["plate"]})

    seconds = time.time() - started
    table = {}
    for key, s in stats.items():
        n = s["n"]
        table[key] = {
            "plates": int(n),
            "raw_ocr_exact_%": round(s["raw_exact"] / n * 100, 1),
            "with_cleanup_exact_%": round(s["ours_exact"] / n * 100, 1),
            "raw_ocr_CER_%": round(s["raw_cer"] / n * 100, 1),
            "with_cleanup_CER_%": round(s["ours_cer"] / n * 100, 1),
            "accepted_%": round(s["accepted"] / n * 100, 1),
            "precision_of_accepted_%": round(s["accepted_right"] / s["accepted"] * 100, 1) if s["accepted"] else None,
        }
    result = {"split": SPLIT, "ocr_engine": "RapidOCR (PP-OCR, ONNX, CPU)", "ms_per_plate": round(seconds / len(labels) * 1000, 1),
              "levels": LEVELS, "results": table, "examples_fixed_by_cleanup": examples}
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", f"plates_{SPLIT}.json"), "w") as f:
        json.dump(result, f, indent=2)

    print(f"{'group':<18}{'n':>5}{'raw exact':>11}{'+cleanup':>10}{'raw CER':>9}{'+cleanup':>10}{'accepted':>10}{'precision':>11}")
    order = ["all"] + [f"level {i}" for i in range(4)] + ["punjab_car", "punjab_bike", "punjab_year", "ict", "sindh"]
    for key in order:
        r = table[key]
        print(f"{key:<18}{r['plates']:>5}{r['raw_ocr_exact_%']:>10}%{r['with_cleanup_exact_%']:>9}%"
              f"{r['raw_ocr_CER_%']:>8}%{r['with_cleanup_CER_%']:>9}%{r['accepted_%']:>9}%"
              f"{str(r['precision_of_accepted_%']):>10}%")
    print(f"\n{result['ms_per_plate']} ms per plate on this CPU. Saved evaluation/results/plates_{SPLIT}.json")


if __name__ == "__main__":
    main()
