"""
evidence.py - Makes the evidence photos for a violation, with privacy protection.

For each violation we keep 3 images:
  * evidence : the whole frame, the offending bike in red, its plate in yellow
  * crop     : just the offending motorcyclist
  * plate    : just the number plate (for the officer to double-check the OCR)

Privacy: everyone who did NOT break a rule is anonymised in the evidence photo:
their heads and their number plates are blurred. Only the offender stays clear.

Used by: app/services/analyzer.py
"""
import cv2

from app.services.plates import crop_box

RED, GREEN, YELLOW, WHITE = (40, 40, 220), (60, 180, 60), (0, 210, 255), (255, 255, 255)
LABELS = {"NO_HELMET": "NO HELMET", "TRIPLE_RIDING": "TRIPLE RIDING"}


def blur_region(image, box):
    x1, y1, x2, y2 = [int(v) for v in box]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(image.shape[1], x2), min(image.shape[0], y2)
    if x2 - x1 < 2 or y2 - y1 < 2:
        return
    region = image[y1:y2, x1:x2]
    k = max(15, ((max(x2 - x1, y2 - y1) // 3) | 1))      # kernel must be odd
    image[y1:y2, x1:x2] = cv2.GaussianBlur(region, (k, k), 0)


def _label(image, text, x, y, colour):
    scale = max(0.5, image.shape[1] / 1600)
    thickness = max(1, int(scale * 2))
    (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
    y = max(th + 6, int(y))
    cv2.rectangle(image, (int(x), y - th - 6), (int(x) + tw + 6, y), colour, -1)
    cv2.putText(image, text, (int(x) + 3, y - 4), cv2.FONT_HERSHEY_SIMPLEX, scale, WHITE, thickness, cv2.LINE_AA)


def _box(image, box, colour):
    thickness = max(2, image.shape[1] // 500)
    x1, y1, x2, y2 = [int(v) for v in box]
    cv2.rectangle(image, (x1, y1), (x2, y2), colour, thickness)


def make_evidence(frame, bikes, offender_index, violation_type, plate_text=None):
    """Return (evidence_image, motorcyclist_crop, plate_crop)."""
    blurred = frame.copy()
    offender = bikes[offender_index]

    for i, bike in enumerate(bikes):                     # anonymise everyone else first
        if i == offender_index:
            continue
        for head in bike["heads"]:
            blur_region(blurred, head["box"])
        for plate in bike["plates"]:
            blur_region(blurred, plate["box"])

    image = blurred.copy()
    _box(image, offender["box"], RED)
    _label(image, LABELS.get(violation_type, violation_type), offender["box"][0], offender["box"][1], RED)
    for head in offender["heads"]:
        _box(image, head["box"], RED if head["role"] == "no_helmet" else GREEN)
    plate_crop = None
    if offender["plates"]:
        plate_box = offender["plates"][0]["box"]
        plate_crop = crop_box(frame, plate_box, pad=0.1)
        _box(image, plate_box, YELLOW)
        if plate_text:
            _label(image, plate_text, plate_box[0], plate_box[3] + 30, (0, 140, 200))

    crop = crop_box(blurred, offender["box"], pad=0.05)
    return image, crop, plate_crop
