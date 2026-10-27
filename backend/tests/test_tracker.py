"""Tracking bikes through video frames: one bike = one violation, plate voting."""
from app import config
from app.services.analyzer import VideoSession
from tests.conftest import FakeDetector, FakeReader, det


def moving_bike(x, head="no_helmet", plate=True):
    d = [det("motorcyclist", (x, 100, x + 200, 400)), det(head, (x + 70, 110, x + 120, 160), 0.8)]
    if plate:
        d.append(det("plate", (x + 70, 340, x + 130, 370)))
    return d


def run(frames, reader, blank_frame):
    session = VideoSession(FakeDetector(frames), reader)
    for i in range(len(frames)):
        session.feed(blank_frame, i * 0.2)
    return session, session.finish()


def test_one_bike_many_frames_gives_one_violation(blank_frame):
    session, violations = run([moving_bike(50 + i * 10) for i in range(8)], FakeReader(), blank_frame)
    assert len(violations) == 1
    assert violations[0]["type"] == "NO_HELMET"
    assert violations[0]["plate"]["plate"] == "LEA-1234"
    assert session.tracker.total_tracks() == 1


def test_two_bikes_two_violations(blank_frame):
    frames = [moving_bike(10 + i * 5) + moving_bike(400 - i * 5) for i in range(5)]
    _, violations = run(frames, FakeReader(), blank_frame)
    assert len(violations) == 2


def test_single_glitch_frame_is_not_reported(blank_frame):
    """No helmet in only 1 of 6 frames = probably a model mistake."""
    frames = [moving_bike(50 + i * 10, head="helmet") for i in range(6)]
    frames[3] = moving_bike(80, head="no_helmet")
    _, violations = run(frames, FakeReader(), blank_frame)
    assert config.MIN_VIOLATION_FRAMES >= 2 and violations == []


def test_plate_voting_picks_the_most_common_reading(blank_frame):
    class ChangingReader(FakeReader):
        readings = ["LEA-1234", "LEA-1284", "LEA-1234", "LEA-1234", "LFA-1234"]

        def read(self, crop):
            text = self.readings[self.calls % len(self.readings)]
            self.calls += 1
            return {"plate": text, "valid": True, "raw": text, "confidence": 0.8}

    _, violations = run([moving_bike(50 + i * 10) for i in range(5)], ChangingReader(), blank_frame)
    assert violations[0]["plate"]["plate"] == "LEA-1234"


def test_plate_reads_are_limited_per_bike(blank_frame):
    reader = FakeReader()
    run([moving_bike(50 + i * 2) for i in range(30)], reader, blank_frame)
    assert reader.calls <= 8


def test_bike_that_leaves_and_new_bike_get_new_track(blank_frame):
    frames = [moving_bike(10)] * 3 + [[]] * (config.TRACK_MAX_MISSING + 2) + [moving_bike(400)] * 3
    session, violations = run(frames, FakeReader(), blank_frame)
    assert session.tracker.total_tracks() == 2 and len(violations) == 2


def test_scene_cut_starts_new_tracks(blank_frame):
    """Edited video: same position, different place -> a different bike, not the same track."""
    import numpy as np
    other_scene = np.full_like(blank_frame, 230)
    frames = [moving_bike(50)] * 4
    session = VideoSession(FakeDetector(frames), FakeReader())
    for i, frame in enumerate([blank_frame, blank_frame, other_scene, other_scene]):
        session.feed(frame, i * 0.2)
    violations = session.finish()
    assert session.scene_cuts == 1
    assert session.tracker.total_tracks() == 2 and len(violations) == 2
