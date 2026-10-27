"""
job_queue.py - Runs photo/video analysis in the background, one job at a time.

Why one at a time? An 8 GB CPU laptop is fastest when the model is not
fighting itself for memory. Jobs wait in a queue; the Jobs table shows
their progress (the frontend polls GET /jobs/{id}).

Used by: app/routes/job_routes.py, main.py (start_worker)
"""
import logging
import queue
import threading
import time

import cv2

from app.database import execute_query
from app.services import analyzer
from app.services.storage import save_violation

log = logging.getLogger("jobs")
_queue = queue.Queue()
_worker = None


def set_progress(job_id, progress, stage, status="running"):
    execute_query("UPDATE Jobs SET status = ?, progress = ?, stage = ? WHERE job_id = ?",
                  (status, progress, stage[:100], job_id), commit=True)


def run_job(job_id: int):
    job = execute_query("SELECT job_id, kind, stored_path, camera_id FROM Jobs WHERE job_id = ?",
                        (job_id,), fetch_one=True)
    if not job:
        return
    started = time.time()
    set_progress(job_id, 1, "Loading the AI model")
    try:
        if job["kind"] == "image":
            image = cv2.imread(job["stored_path"])
            set_progress(job_id, 30, "Detecting motorcyclists, helmets and plates")
            result = analyzer.analyse_image(image)
            violations, bikes = result["violations"], len(result["bikes"])
        else:
            result = analyzer.analyse_video(job["stored_path"],
                                            progress=lambda p, s: set_progress(job_id, p, s))
            violations, bikes = result["violations"], result["motorcyclists"]

        set_progress(job_id, 97, "Saving evidence")
        for v in violations:
            save_violation(job_id, job["camera_id"], v)

        execute_query(
            """UPDATE Jobs SET status = 'done', progress = 100, stage = 'Finished', motorcyclists = ?,
                   violations = ?, seconds_taken = ?, finished_at = SYSDATETIME() WHERE job_id = ?""",
            (bikes, len(violations), round(time.time() - started, 1), job_id), commit=True)
        log.info("Job %s done: %s bikes, %s violations", job_id, bikes, len(violations))
    except Exception as e:
        log.exception("Job %s failed", job_id)
        message = str(e) if isinstance(e, (FileNotFoundError, ValueError)) else "Analysis failed. See logs/backend.log."
        execute_query("UPDATE Jobs SET status = 'failed', stage = 'Failed', error = ?, finished_at = SYSDATETIME() "
                      "WHERE job_id = ?", (message[:400], job_id), commit=True)


def _loop():
    while True:
        job_id = _queue.get()
        try:
            run_job(job_id)
        finally:
            _queue.task_done()


def enqueue(job_id: int):
    _queue.put(job_id)


def start_worker():
    """Start the background thread, and re-queue jobs left unfinished by a restart."""
    global _worker
    if _worker is not None:
        return
    _worker = threading.Thread(target=_loop, name="job-worker", daemon=True)
    _worker.start()
    try:
        left = execute_query("SELECT job_id FROM Jobs WHERE status IN ('queued', 'running') AND kind <> 'live' "
                             "ORDER BY job_id", fetch_all=True) or []
        for row in left:
            enqueue(row["job_id"])
        if left:
            log.info("Re-queued %s unfinished jobs", len(left))
    except Exception:
        log.exception("Could not re-queue old jobs")
