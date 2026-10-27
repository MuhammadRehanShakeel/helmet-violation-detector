"""
plates.py - Reads Pakistani number plates (offline OCR) and cleans the text.

Two parts:
  * read_plate(crop)      - RapidOCR (PaddleOCR models in ONNX format, runs on CPU) reads the text
  * normalise_plate(text) - turns messy OCR text into a clean registration number

Why normalise? OCR on small, blurry plates makes typical mistakes:
    "PUNJAB LEA 1234"  -> the word PUNJAB is not part of the number
    "LE4-I234"         -> 4 should be A (letter part), I should be 1 (number part)
    "LEA 19 1234"      -> 19 is the registration year, not part of the number
Pakistani plates are LETTERS (2-4) followed by DIGITS (1-4), so we know which
part must be letters and which must be digits, and fix the common look-alikes.

Used by: app/services/analyzer.py, evaluation/eval_plates.py
"""
import logging
import re
import threading

import cv2
import numpy as np

from app import config

log = logging.getLogger("plates")

TO_LETTER = {"0": "O", "1": "I", "2": "Z", "4": "A", "5": "S", "6": "G", "7": "T", "8": "B"}
TO_DIGIT = {"O": "0", "Q": "0", "D": "0", "U": "0", "I": "1", "L": "1", "J": "1", "Z": "2",
            "S": "5", "B": "8", "G": "6", "T": "7", "A": "4"}
IGNORE = set(config.PLATE_IGNORE_WORDS)


def _edit_distance(a: str, b: str) -> int:
    row = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        prev, row[0] = row[0], i
        for j, cb in enumerate(b, 1):
            prev, row[j] = row[j], min(row[j] + 1, row[j - 1] + 1, prev + (ca != cb))
    return row[len(b)]


def _is_ignored(token: str) -> bool:
    """PUNJAB, and OCR misreads of it like PUNIAB / PUNJAG, are not part of the number."""
    if token in IGNORE:
        return True
    return len(token) >= 5 and any(len(w) >= 5 and _edit_distance(token, w) <= 2 for w in IGNORE)


def _tokens(text: str):
    """'PUNJAB  lea-19 1234' -> ['LEA', '19', '1234'] (province words removed)."""
    text = re.sub(r"[.:,'`]", "", (text or "").upper())          # 'PUNJA.B' -> 'PUNJAB'
    parts = re.split(r"[^A-Z0-9]+", text)
    return [p for p in parts if p and not _is_ignored(p)]


def _fix_doubled_digits(tokens):
    """
    OCR often repeats the first digit of the number at the end of the token before it,
    because of the wide gap on plates:  'HU5 552' -> 'HU 552',  'RIL 8 833' -> 'RIL 833'.
    """
    fixed = list(tokens)
    i = 0
    while i < len(fixed) - 1:
        current, nxt = fixed[i], fixed[i + 1]
        if nxt.isdigit() and current[-1].isdigit() and current[-1] == nxt[0]:
            if len(current) == 1:
                fixed.pop(i)
                continue
            fixed[i] = current[:-1]
        i += 1
    return fixed


def _split(joined: str, boundaries=()):
    """
    Try every split 'LETTERS|DIGITS' and keep the one that needs the fewest fixes.
    `boundaries` = where the OCR saw a space; splitting there is more likely right.
    Returns (letters, digits, fixes) or None.
    """
    best = None
    for k in (3, 2, 4):                                # 3 letters is the most common in Pakistan
        if len(joined) <= k:
            continue
        head, tail = joined[:k], joined[k:]
        letters = "".join(c if c.isalpha() else TO_LETTER.get(c, "?") for c in head)
        digits = "".join(c if c.isdigit() else TO_DIGIT.get(c, "?") for c in tail)
        if "?" in letters or "?" in digits or not any(c.isalpha() for c in head):
            continue
        fixes = sum(1 for c in head if not c.isalpha()) + sum(1 for c in tail if not c.isdigit())
        if len(digits) in (5, 6):                      # "LEA191234": first 2 digits are the year
            digits = digits[2:]
            fixes += 1                                 # a guess, so prefer readings that need no year cut
        if boundaries and k not in boundaries:
            fixes += 1                                 # OCR saw a gap somewhere else
        if not 1 <= len(digits) <= 4:
            continue
        if k == 4:
            fixes += 1                                 # 4-letter codes are rare in Pakistan
        if best is None or fixes < best[2]:
            best = (letters, digits, fixes)
    return best


def normalise_plate(text: str):
    """
    Returns {"plate": "LEA-1234" or None, "valid": bool, "fixes": int}
    """
    tokens = _tokens(text)
    if not tokens:
        return {"plate": None, "valid": False, "fixes": 0}

    tokens = _fix_doubled_digits(tokens)

    # The small registration year is not part of the number:
    #   LEA 19 1234 -> LEA 1234      FDA19 1080 -> FDA 1080
    number_tokens = [t for t in tokens if t.isdigit()]
    if number_tokens and len(number_tokens[-1]) >= 3:
        last = tokens[-1]
        for i, t in enumerate(tokens[:-1]):
            if t.isdigit() and len(t) == 2 and last.isdigit():
                tokens.pop(i)
                break
            glued = re.fullmatch(r"([A-Z]{2,4})(\d{2})", t)
            if glued and last.isdigit():
                tokens[i] = glued.group(1)
                break

    joined = "".join(tokens)
    boundaries, position = set(), 0
    for t in tokens[:-1]:
        position += len(t)
        boundaries.add(position)
    result = _split(joined, boundaries)
    if result is None:
        cleaned = joined[:12] if joined else None
        return {"plate": cleaned, "valid": False, "fixes": 0}
    letters, digits, fixes = result
    return {"plate": f"{letters}-{digits}", "valid": True, "fixes": fixes}


def compact(plate: str) -> str:
    """For searching: 'lea 1234' and 'LEA-1234' both become 'LEA1234'."""
    return re.sub(r"[^A-Z0-9]", "", (plate or "").upper())


# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------
class PlateReader:
    def __init__(self):
        self.engine = None
        self._lock = threading.Lock()

    def load(self):
        if self.engine is None:
            with self._lock:
                if self.engine is None:
                    from rapidocr_onnxruntime import RapidOCR
                    self.engine = RapidOCR()
                    log.info("Plate OCR loaded (RapidOCR, offline)")

    @staticmethod
    def prepare(crop):
        """Make small plates bigger and clearer before OCR."""
        h, w = crop.shape[:2]
        if h < 96:
            factor = 96 / max(h, 1)
            crop = cv2.resize(crop, (int(w * factor), 96), interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4)).apply(gray)
        padded = cv2.copyMakeBorder(gray, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255)
        return cv2.cvtColor(padded, cv2.COLOR_GRAY2BGR)

    def ocr_text(self, crop):
        """Raw OCR: returns (text in reading order, mean confidence)."""
        self.load()
        result, _ = self.engine(self.prepare(crop))
        if not result:
            return "", 0.0
        items = []
        for box, text, conf in result:
            ys = [p[1] for p in box]
            xs = [p[0] for p in box]
            items.append({"text": text, "conf": float(conf), "y": sum(ys) / 4, "x": min(xs),
                          "h": max(ys) - min(ys)})
        # reading order: top line first (two-line motorcycle plates), then left to right
        line_height = max(i["h"] for i in items) * 0.6
        items.sort(key=lambda i: (round(i["y"] / max(line_height, 1)), i["x"]))
        text = " ".join(i["text"] for i in items)
        return text, sum(i["conf"] for i in items) / len(items)

    def read(self, crop):
        """
        Full plate reading. Returns
          {"plate", "valid", "raw", "confidence"}
        A plate is only accepted if OCR is confident enough.
        """
        if crop is None or crop.size == 0 or min(crop.shape[:2]) < 8:
            return {"plate": None, "valid": False, "raw": "", "confidence": 0.0}
        raw, conf = self.ocr_text(crop)
        cleaned = normalise_plate(raw)
        if conf < config.PLATE_MIN_CONFIDENCE:
            cleaned["valid"] = False
        return {"plate": cleaned["plate"], "valid": cleaned["valid"], "raw": raw[:60], "confidence": round(conf, 3)}


plate_reader = PlateReader()


def crop_box(image, box, pad: float = 0.08):
    """Cut a box out of the image with a little extra margin."""
    h, w = image.shape[:2]
    x1, y1, x2, y2 = box
    px, py = (x2 - x1) * pad, (y2 - y1) * pad
    x1, y1 = int(max(0, x1 - px)), int(max(0, y1 - py))
    x2, y2 = int(min(w, x2 + px)), int(min(h, y2 + py))
    if x2 <= x1 or y2 <= y1:
        return np.zeros((0, 0, 3), dtype=np.uint8)
    return image[y1:y2, x1:x2].copy()
