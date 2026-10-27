"""
job_routes.py - Upload a photo or video for analysis, and follow its progress.

  POST /jobs            (officer) multipart: file, camera_id   -> {job_id}
  GET  /jobs            (officer) my jobs (admins see everyone's)
  GET  /jobs/{job_id}   (officer) progress of one job
"""
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.core.auth import OFFICER
from app.database import execute_insert_and_get_id, execute_query
from app.routes.camera_routes import get_camera_or_404
from app.services import job_queue
from app.services.storage import save_upload

router = APIRouter(prefix="/jobs", tags=["Analysis jobs"])
JOB_COLUMNS = """j.job_id, j.kind, j.original_name, j.status, j.progress, j.stage, j.motorcyclists, j.violations,
                 j.seconds_taken, j.error, j.created_at, j.finished_at, j.camera_id, c.name AS camera_name,
                 u.full_name AS uploaded_by"""


@router.post("", status_code=201)
def create_job(file: UploadFile = File(...), camera_id: Optional[int] = Form(None),
               current_user: dict = Depends(OFFICER)):
    get_camera_or_404(camera_id)
    kind, path = save_upload(file)
    name = (file.filename or "upload")[-200:]
    job_id = execute_insert_and_get_id(
        "INSERT INTO Jobs (user_id, camera_id, kind, original_name, stored_path, stage) OUTPUT INSERTED.job_id "
        "VALUES (?, ?, ?, ?, ?, 'Waiting in queue')", (current_user["user_id"], camera_id, kind, name, path))
    job_queue.enqueue(job_id)
    return {"job_id": job_id, "kind": kind}


def _visible_job(job_id: int, current_user: dict):
    job = execute_query(
        f"""SELECT {JOB_COLUMNS}, j.user_id FROM Jobs j LEFT JOIN Cameras c ON j.camera_id = c.camera_id
            JOIN Users u ON j.user_id = u.user_id WHERE j.job_id = ?""", (job_id,), fetch_one=True)
    if not job or (current_user["role"] != "admin" and job["user_id"] != current_user["user_id"]):
        raise HTTPException(404, "Job not found.")             # 404, not 403: do not reveal it exists
    return job


@router.get("")
def list_jobs(limit: int = 50, current_user: dict = Depends(OFFICER)):
    limit = max(1, min(limit, 200))
    where, params = ("", ()) if current_user["role"] == "admin" else ("WHERE j.user_id = ?", (current_user["user_id"],))
    return execute_query(
        f"""SELECT TOP ({limit}) {JOB_COLUMNS} FROM Jobs j LEFT JOIN Cameras c ON j.camera_id = c.camera_id
            JOIN Users u ON j.user_id = u.user_id {where} ORDER BY j.job_id DESC""", params, fetch_all=True) or []


@router.get("/{job_id}")
def get_job(job_id: int, current_user: dict = Depends(OFFICER)):
    job = _visible_job(job_id, current_user)
    job.pop("user_id", None)
    return job
