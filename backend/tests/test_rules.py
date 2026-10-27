"""Turning boxes into violations (pure logic)."""
from app.services.rules import analyse_detections, iou
from tests.conftest import det

BIKE = (100, 100, 300, 400)


def test_iou():
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1
    assert iou((0, 0, 10, 10), (20, 20, 30, 30)) == 0


def test_rider_with_helmet_is_ok():
    bikes = analyse_detections([det("motorcyclist", BIKE), det("helmet", (170, 110, 220, 160))])
    assert bikes[0]["status"] == "ok" and bikes[0]["violations"] == []


def test_rider_without_helmet():
    bikes = analyse_detections([det("motorcyclist", BIKE), det("no_helmet", (170, 110, 220, 160), 0.8)])
    assert [v["type"] for v in bikes[0]["violations"]] == ["NO_HELMET"]
    assert bikes[0]["violations"][0]["confidence"] == 0.8


def test_pillion_without_helmet_counts():
    bikes = analyse_detections([det("motorcyclist", BIKE), det("helmet", (150, 110, 190, 150)),
                                det("no_helmet", (210, 120, 250, 160))])
    assert bikes[0]["riders"] == 2 and bikes[0]["no_helmet_count"] == 1
    assert bikes[0]["violations"][0]["type"] == "NO_HELMET"


def test_triple_riding():
    heads = [det("helmet", (110 + i * 60, 110, 150 + i * 60, 150)) for i in range(3)]
    bikes = analyse_detections([det("motorcyclist", BIKE)] + heads)
    assert [v["type"] for v in bikes[0]["violations"]] == ["TRIPLE_RIDING"]


def test_triple_riding_and_no_helmet_together():
    heads = [det("helmet", (110, 110, 150, 150)), det("no_helmet", (170, 110, 210, 150)),
             det("no_helmet", (230, 110, 270, 150))]
    types = {v["type"] for v in analyse_detections([det("motorcyclist", BIKE)] + heads)[0]["violations"]}
    assert types == {"NO_HELMET", "TRIPLE_RIDING"}


def test_no_heads_means_unclear_not_violation():
    bikes = analyse_detections([det("motorcyclist", BIKE)])
    assert bikes[0]["status"] == "unclear" and bikes[0]["violations"] == []


def test_head_outside_any_bike_is_ignored():
    """A pedestrian's bare head must never create a violation."""
    bikes = analyse_detections([det("motorcyclist", BIKE), det("no_helmet", (500, 100, 540, 140))])
    assert bikes[0]["status"] == "unclear"


def test_duplicate_head_boxes_keep_the_surer_one():
    bikes = analyse_detections([det("motorcyclist", BIKE), det("helmet", (170, 110, 220, 160), 0.9),
                                det("no_helmet", (172, 112, 220, 160), 0.4)])
    assert bikes[0]["riders"] == 1 and bikes[0]["status"] == "ok"


def test_each_head_and_plate_goes_to_the_right_bike():
    left, right = (0, 100, 200, 400), (220, 100, 420, 400)
    bikes = analyse_detections([
        det("motorcyclist", left), det("motorcyclist", right),
        det("helmet", (60, 110, 110, 160)), det("no_helmet", (290, 110, 340, 160)),
        det("plate", (70, 340, 130, 370)), det("plate", (290, 340, 350, 370)),
    ])
    by_x = sorted(bikes, key=lambda b: b["box"][0])
    assert by_x[0]["status"] == "ok" and by_x[1]["status"] == "violation"
    assert by_x[0]["plates"][0]["box"][0] == 70 and by_x[1]["plates"][0]["box"][0] == 290


def test_overlapping_bikes_head_goes_to_upper_part():
    """Bike behind another: a head near the top of bike A but the bottom of bike B belongs to A."""
    front, back = (100, 200, 300, 500), (120, 50, 320, 330)
    bikes = analyse_detections([det("motorcyclist", front), det("motorcyclist", back),
                                det("no_helmet", (180, 210, 230, 260))])
    owner = [b for b in bikes if b["heads"]][0]
    assert owner["box"] == list(front)


# --- backup bike finder (COCO model) -------------------------------------
from app.services.rules import bikes_from_coco, has_orphan_heads  # noqa: E402


def coco(label, box, conf=0.8):
    return {"role": None, "label": label, "conf": conf, "box": list(box)}


def test_orphan_head_detection():
    assert has_orphan_heads([det("no_helmet", (10, 10, 50, 50))]) is True
    assert has_orphan_heads([det("motorcyclist", BIKE), det("no_helmet", (170, 110, 220, 160))]) is False


def test_backup_builds_rider_box_from_motorcycle_and_person():
    bikes = bikes_from_coco([coco("motorcycle", (100, 250, 300, 450)), coco("person", (140, 80, 260, 400))], [])
    assert len(bikes) == 1 and bikes[0]["box"] == [100, 80, 300, 450]
    # the head that was an orphan now belongs to this bike
    result = analyse_detections(bikes + [det("no_helmet", (180, 90, 220, 130))])
    assert result[0]["violations"][0]["type"] == "NO_HELMET"


def test_backup_ignores_people_not_on_the_bike_and_known_bikes():
    walker = coco("person", (500, 80, 560, 400))
    bikes = bikes_from_coco([coco("motorcycle", (100, 250, 300, 450)), walker], [])
    assert bikes[0]["box"] == [100, 250, 300, 450]
    assert bikes_from_coco([coco("motorcycle", (100, 250, 300, 450))], [det("motorcyclist", (100, 240, 300, 450))]) == []


def test_pedestrian_head_without_any_bike_stays_ignored():
    bikes = bikes_from_coco([coco("person", (500, 80, 560, 400))], [])
    assert bikes == []
