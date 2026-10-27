"""
camera_routes.py - Camera locations and their CCTV / IP camera streams.

  GET  /cameras                      any user (stream passwords are never shown)
  POST /cameras                      admin
  PUT  /cameras/{camera_id}          admin
  PUT  /cameras/{camera_id}/stream   admin: set the stream address and switch watching on/off
  GET  /cameras/streams/status       officer: which cameras are being watched right now
  GET  /cameras/{camera_id}/snapshot officer: the latest analysed picture (JPEG, with boxes)
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from app.core.auth import ADMIN, ANY_USER, OFFICER
from app.core.security import client_ip
from app.database import execute_insert_and_get_id, execute_query
from app.schemas import CameraIn, StreamSettings
from app.services.audit import audit
from app.services.streams import mask_url, stream_manager, validate_url

router = APIRouter(prefix="/cameras", tags=["Cameras"])


def get_camera_or_404(camera_id):
    if camera_id is None:
        return None
    camera = execute_query("SELECT camera_id, name, location, is_active FROM Cameras WHERE camera_id = ?",
                           (camera_id,), fetch_one=True)
    if not camera or not camera["is_active"]:
        raise HTTPException(404, "Camera not found.")
    return camera


@router.get("")
def list_cameras(current_user: dict = Depends(ANY_USER)):
    rows = execute_query(
        """SELECT c.camera_id, c.name, c.location, c.latitude, c.longitude, c.is_active, c.stream_url,
                  c.stream_enabled, (SELECT COUNT(*) FROM Violations v WHERE v.camera_id = c.camera_id) AS violations
           FROM Cameras c ORDER BY c.camera_id""", fetch_all=True) or []
    live = stream_manager.status()
    for row in rows:
        row["stream_url"] = mask_url(row["stream_url"]) if current_user["role"] == "admin" else None
        row["stream"] = live.get(row["camera_id"])
    return rows


@router.post("", status_code=201)
def create_camera(body: CameraIn, request: Request, current_user: dict = Depends(ADMIN)):
    camera_id = execute_insert_and_get_id(
        "INSERT INTO Cameras (name, location, latitude, longitude, is_active) OUTPUT INSERTED.camera_id "
        "VALUES (?, ?, ?, ?, ?)", (body.name, body.location, body.latitude, body.longitude, 1 if body.is_active else 0))
    audit(current_user["user_id"], "camera_created", body.name, None, client_ip(request))
    return {"camera_id": camera_id}


@router.put("/{camera_id}")
def update_camera(camera_id: int, body: CameraIn, request: Request, current_user: dict = Depends(ADMIN)):
    if not execute_query("SELECT 1 AS x FROM Cameras WHERE camera_id = ?", (camera_id,), fetch_one=True):
        raise HTTPException(404, "Camera not found.")
    execute_query("UPDATE Cameras SET name = ?, location = ?, latitude = ?, longitude = ?, is_active = ? "
                  "WHERE camera_id = ?",
                  (body.name, body.location, body.latitude, body.longitude, 1 if body.is_active else 0, camera_id),
                  commit=True)
    if not body.is_active:
        stream_manager.stop(camera_id)
    audit(current_user["user_id"], "camera_changed", str(camera_id), None, client_ip(request))
    return {"status": "success"}


@router.put("/{camera_id}/stream")
def set_stream(camera_id: int, body: StreamSettings, request: Request, current_user: dict = Depends(ADMIN)):
    camera = execute_query("SELECT camera_id, name, is_active, stream_url FROM Cameras WHERE camera_id = ?",
                           (camera_id,), fetch_one=True)
    if not camera:
        raise HTTPException(404, "Camera not found.")
    url = (body.stream_url or "").strip()
    if "***" in url:                       # the masked address came back unchanged: keep the stored one
        url = camera["stream_url"] or ""
    if url:
        try:
            url = validate_url(url)
        except ValueError as e:
            raise HTTPException(400, str(e))
    if body.stream_enabled and not url:
        raise HTTPException(400, "Enter the camera's stream address first.")
    if body.stream_enabled and not camera["is_active"]:
        raise HTTPException(400, "Switch the camera on (Active) first.")

    stream_manager.stop(camera_id)         # restart with the new settings
    execute_query("UPDATE Cameras SET stream_url = ?, stream_enabled = ? WHERE camera_id = ?",
                  (url or None, 1 if body.stream_enabled else 0, camera_id), commit=True)
    if body.stream_enabled:
        try:
            stream_manager.start(camera_id, camera["name"], url, current_user["user_id"])
        except RuntimeError as e:
            execute_query("UPDATE Cameras SET stream_enabled = 0 WHERE camera_id = ?", (camera_id,), commit=True)
            raise HTTPException(409, str(e))
    audit(current_user["user_id"], "stream_on" if body.stream_enabled else "stream_off", camera["name"],
          mask_url(url), client_ip(request))
    return {"status": "watching" if body.stream_enabled else "stopped", "stream_url": mask_url(url)}


@router.get("/streams/status")
def streams_status(current_user: dict = Depends(OFFICER)):
    return list(stream_manager.status().values())


@router.get("/{camera_id}/snapshot")
def snapshot(camera_id: int, current_user: dict = Depends(OFFICER)):
    jpeg = stream_manager.snapshot(camera_id)
    if not jpeg:
        raise HTTPException(404, "No picture yet from this camera.")
    return Response(jpeg, media_type="image/jpeg", headers={"Cache-Control": "no-store"})
