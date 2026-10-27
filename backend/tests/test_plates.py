"""Number plate clean-up (no OCR model needed)."""
import pytest

from app.services.plates import compact, normalise_plate


@pytest.mark.parametrize("raw, expected", [
    ("LEA 1234", "LEA-1234"),
    ("lea-1234", "LEA-1234"),
    ("PUNJAB LEA 1234", "LEA-1234"),          # province word removed
    ("LEA 19 1234", "LEA-1234"),               # registration year removed
    ("LE4 I234", "LEA-1234"),                  # 4 -> A in the letter part, I -> 1 in the number part
    ("RIK 5O7", "RIK-507"),                    # O -> 0
    ("ICT AB 123", "AB-123"),                  # Islamabad: ICT is not part of the number
    ("SINDH BJV 456", "BJV-456"),
    ("LHR 12", "LHR-12"),
    ("LEZ\n1234", "LEZ-1234"),                 # two-line motorcycle plate
    ("LEA191234", "LEA-1234"),                 # year glued to the number
    ("PUNIAB SKA 8865", "SKA-8865"),           # misread province word still removed
    ("PUNJA.B LED 6637", "LED-6637"),
    ("ICT HU5 552", "HU-552"),                 # first digit doubled by the OCR
    ("PUNJAB RIL 8 833", "RIL-833"),
    ("PUNJAB FDA191 1080", "FDA-1080"),        # year glued to the letters + doubled digit
    ("PUNJAB RIM1 15 8072", "RIM-8072"),
    ("ICT SD 894", "SD-894"),                  # SD can be real letters
])
def test_valid_plates(raw, expected):
    result = normalise_plate(raw)
    assert result["valid"] is True
    assert result["plate"] == expected


@pytest.mark.parametrize("raw", ["", "PUNJAB", "1234", "ABCDEFGH", "?!", "L"])
def test_invalid_plates(raw):
    assert normalise_plate(raw)["valid"] is False


def test_fix_counter():
    assert normalise_plate("LEA 1234")["fixes"] == 0
    assert normalise_plate("LE4 I234")["fixes"] == 2


def test_compact_for_search():
    assert compact("lea - 1234") == compact("LEA-1234") == "LEA1234"
