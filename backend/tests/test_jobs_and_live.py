"""Background jobs and the live camera, with a fake model and fake database."""
import os

import cv2
import numpy as np

from app import config
from app.services import analyzer, job_queue, live
from tests.conftest import FakeDetector, FakeReader, det

OFFENDER = [det("motorcyclist", (20, 100, 220, 450)), det("no_helmet", (90, 110, 140, 160), 0.85),
            det("plate", (90, 400, 150, 430))]


def use_fakes(monkeypatch, detections):
    monkeypatch.setattr(analyzer, "default_detector", FakeDetector(detections))
    monkeypatch.setattr(analyzer, "default_reader", FakeReader())
    monkeypatch.setattr(analyzer, "default_helper", None)


def test_image_job_saves_violation_and_evidence(fake_db, monkeypatch, tmp_path, blank_frame):
    use_fakes(monkeypatch, OFFENDER)
    path = str(tmp_path / "road.jpg")
    cv2.imwrite(path, blank_frame)
    fake_db.on("FROM Jobs WHERE job_id = ?", {"job_id": 1, "kind": "image", "stored_path": path, "camera_id": 2})
    job_queue.run_job(1)
    insert = fake_db.ran("INSERT INTO Violations")
    assert len(insert) == 1
    params = insert[0][1]
    assert params[2] == "NO_HELMET" and params[7] == "LEA-1234"
    for name in params[-3:]:                                   # evidence, crop, plate images exist
        assert os.path.exists(os.path.join(config.EVIDENCE_DIR, name))
    done = fake_db.ran("SET status = 'done'")[0][1]
    assert done[0] == 1 and done[1] == 1                       # 1 bike, 1 violation


def test_failed_job_is_marked_failed_not_crashing(fake_db, monkeypatch, tmp_path):
    fake_db.on("FROM Jobs WHERE job_id = ?", {"job_id": 1, "kind": "video", "stored_path": str(tmp_path / "x.mp4"),
                                              "camera_id": None})
    job_queue.run_job(1)
    failed = fake_db.ran("SET status = 'failed'")
    assert failed and "could not be opened" in failed[0][1][0]


def test_live_session_reports_each_bike_once(fake_db, monkeypatch, blank_frame):
    use_fakes(monkeypatch, OFFENDER)
    job_id = live.start(user_id=2, camera_id=None)
    session = live.get(job_id, 2)
    assert live.get(job_id, 99) is None                        # another user cannot use this session
    first = live.process_frame(session, blank_frame)
    assert first["new_violations"] == []                        # 1 frame is not enough proof yet
    new_total = 0
    for _ in range(5):
        result = live.process_frame(session, blank_frame)
        new_total += len(result["new_violations"])
    assert new_total == 1 and result["total_violations"] == 1
    assert result["bikes"][0]["status"] == "violation"
    assert live.stop(session) == 1
    assert live.get(job_id, 2) is None


def test_live_frame_must_be_an_image():
    import pytest
    from fastapi import HTTPException
    from app.services.storage import decode_image_bytes
    with pytest.raises(HTTPException):
        decode_image_bytes(b"not an image at all")
    ok, jpg = cv2.imencode(".jpg", np.zeros((40, 40, 3), np.uint8))
    assert decode_image_bytes(jpg.tobytes()).shape == (40, 40, 3)
