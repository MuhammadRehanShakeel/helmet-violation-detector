"""Photo analysis end-to-end with a fake model: evidence images and privacy blur."""
import numpy as np

from app.services.analyzer import analyse_image
from app.services.detector import decode, letterbox, role_for
from tests.conftest import FakeDetector, FakeReader, det

OFFENDER = [det("motorcyclist", (20, 100, 220, 450)), det("no_helmet", (90, 110, 140, 160), 0.85),
            det("plate", (90, 400, 150, 430))]
GOOD_RIDER = [det("motorcyclist", (400, 100, 600, 450)), det("helmet", (470, 110, 520, 160)),
              det("plate", (470, 400, 530, 430))]


def test_photo_with_offender_and_good_rider(blank_frame):
    result = analyse_image(blank_frame, FakeDetector(OFFENDER + GOOD_RIDER), FakeReader())
    assert len(result["bikes"]) == 2
    assert len(result["violations"]) == 1
    v = result["violations"][0]
    assert v["type"] == "NO_HELMET" and v["plate"]["plate"] == "LEA-1234"
    assert v["evidence"].shape == blank_frame.shape
    assert v["crop"].size > 0 and v["plate_crop"].size > 0
    assert v["low_confidence"] is False


def test_good_riders_are_blurred_in_evidence(blank_frame):
    v = analyse_image(blank_frame, FakeDetector(OFFENDER + GOOD_RIDER), FakeReader())["violations"][0]
    good_head = (slice(115, 155), slice(475, 515))
    good_plate = (slice(402, 428), slice(472, 528))
    assert not np.array_equal(v["evidence"][good_head], blank_frame[good_head])
    assert not np.array_equal(v["evidence"][good_plate], blank_frame[good_plate])


def test_plates_are_read_only_for_offenders(blank_frame):
    reader = FakeReader()
    analyse_image(blank_frame, FakeDetector(GOOD_RIDER), reader)
    assert reader.calls == 0


def test_low_confidence_flag(blank_frame):
    weak = [det("motorcyclist", (20, 100, 220, 450)), det("no_helmet", (90, 110, 140, 160), 0.4)]
    v = analyse_image(blank_frame, FakeDetector(weak), FakeReader())["violations"][0]
    assert v["low_confidence"] is True and v["plate"] is None


def test_class_names_from_different_datasets():
    assert role_for("WithoutHelmet") == "no_helmet"
    assert role_for("licenseplate") == "plate"
    assert role_for("Motorcyclist") == "motorcyclist"
    assert role_for("car") is None


def test_letterbox_keeps_aspect_ratio():
    canvas, scale, pad_x, pad_y = letterbox(np.zeros((480, 640, 3), np.uint8), 640)
    assert canvas.shape == (640, 640, 3) and scale == 1.0 and pad_x == 0 and pad_y == 80


def test_decode_maps_boxes_back_and_removes_duplicates():
    """Fake raw model output: 2 overlapping 'helmet' boxes + 1 'plate' box."""
    names = {0: "helmet", 1: "plate"}
    output = np.zeros((1, 6, 4), np.float32)
    # columns: cx, cy, w, h, score_helmet, score_plate
    output[0, :, 0] = [320, 400, 100, 100, 0.9, 0.0]
    output[0, :, 1] = [322, 402, 100, 100, 0.7, 0.0]     # duplicate of box 0
    output[0, :, 2] = [100, 500, 60, 20, 0.0, 0.8]
    output[0, :, 3] = [50, 50, 10, 10, 0.1, 0.0]         # too weak
    dets = decode(output, scale=1.0, pad_x=0, pad_y=80, image_w=640, image_h=480,
                  names=names, conf_threshold=0.3, iou_threshold=0.5)
    assert [d["role"] for d in dets] == ["helmet", "plate"]
    assert dets[0]["box"] == [270.0, 270.0, 370.0, 370.0]   # y moved up by the 80 px padding


def test_backup_model_only_runs_when_a_head_has_no_bike(blank_frame):
    class Helper(FakeDetector):
        pass
    head_only = [det("no_helmet", (180, 90, 220, 130), 0.8)]
    helper = Helper([{"role": None, "label": "motorcycle", "conf": 0.8, "box": [100, 250, 300, 450]},
                     {"role": None, "label": "person", "conf": 0.8, "box": [140, 80, 260, 400]}])
    result = analyse_image(blank_frame, FakeDetector(head_only), FakeReader(), helper)
    assert len(result["violations"]) == 1 and helper.calls == 1

    helper2 = Helper([])
    analyse_image(blank_frame, FakeDetector(OFFENDER), FakeReader(), helper2)
    assert helper2.calls == 0                       # main model already found the bike
