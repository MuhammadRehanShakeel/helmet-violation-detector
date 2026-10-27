"""
live.py - The live camera: the phone/webcam sends ~1 frame per second.

Each live session keeps its own tracker (VideoSession), so a bike that stays in
view is reported only once. Violations are saved as soon as they are confirmed.
Sessions that stop sending frames for LIVE_IDLE_SECONDS are closed automatically.

Used by: app/routes/live_routes.py
"""
import threading
import time

from app.database import execute_insert_and_get_id, execute_query
from app.services.analyzer import VideoSession, public_bike
from app.services.storage import save_violation

LIVE_IDLE_SECONDS = 120
_sessions = {}
_lock = threading.Lock()


class LiveSession:
    def __init__(self, job_id, camera_id, user_id):
        self.job_id = job_id
        self.camera_id = camera_id
        self.user_id = user_id
        self.video = VideoSession()
        self.started = time.time()
        self.last_seen = time.time()
        self.saved = 0
        self.lock = threading.Lock()                 # one frame at a time per session


def start(user_id: int, camera_id) -> int:
    job_id = execute_insert_and_get_id(
        "INSERT INTO Jobs (user_id, camera_id, kind, original_name, status, stage) OUTPUT INSERTED.job_id "
        "VALUES (?, ?, 'live', 'Live camera', 'running', 'Live')", (user_id, camera_id))
    with _lock:
        _sessions[job_id] = LiveSession(job_id, camera_id, user_id)
    return job_id


def get(job_id: int, user_id: int):
    """Only the user who started a live session may send frames to it."""
    _cleanup()
    with _lock:
        session = _sessions.get(job_id)
    if session is None or session.user_id != user_id:
        return None
    return session


def process_frame(session: LiveSession, frame):
    with session.lock:
        session.last_seen = time.time()
        frame_time = round(time.time() - session.started, 1)
        bikes, _ = session.video.feed(frame, frame_time)
        new = session.video.collect(list(session.video.tracker.tracks.values()), finished=False)
        ids = [save_violation(session.job_id, session.camera_id, v) for v in new]
        session.saved += len(ids)
        return {
            "bikes": [public_bike(b) for b in bikes],
            "new_violations": [{"violation_id": i, "type": v["type"],
                                "plate": (v["plate"] or {}).get("plate")} for i, v in zip(ids, new)],
            "total_violations": session.saved,
            "motorcyclists": session.video.tracker.total_tracks(),
        }


def stop(session: LiveSession):
    with session.lock:
        new = session.video.finish()
        for v in new:
            save_violation(session.job_id, session.camera_id, v)
        session.saved += len(new)
        execute_query(
            """UPDATE Jobs SET status = 'done', progress = 100, stage = 'Finished', motorcyclists = ?,
                   violations = ?, seconds_taken = ?, finished_at = SYSDATETIME() WHERE job_id = ?""",
            (session.video.tracker.total_tracks(), session.saved, round(time.time() - session.started, 1),
             session.job_id), commit=True)
    with _lock:
        _sessions.pop(session.job_id, None)
    return session.saved


def _cleanup():
    now = time.time()
    with _lock:
        idle = [s for s in _sessions.values() if now - s.last_seen > LIVE_IDLE_SECONDS]
    for session in idle:
        stop(session)
