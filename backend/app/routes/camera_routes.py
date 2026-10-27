"""
camera_routes.py - Camera locations (where a photo/video/live feed comes from).

  GET  /cameras              any user
  POST /cameras              admin
  PUT  /cameras/{camera_id}  admin
"""
from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.auth import ADMIN, ANY_USER
from app.core.security import client_ip
from app.database import execute_insert_and_get_id, execute_query
from app.schemas import CameraIn
from app.services.audit import audit

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
    return execute_query(
        """SELECT c.camera_id, c.name, c.location, c.latitude, c.longitude, c.is_active,
                  (SELECT COUNT(*) FROM Violations v WHERE v.camera_id = c.camera_id) AS violations
           FROM Cameras c ORDER BY c.camera_id""", fetch_all=True) or []


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
    audit(current_user["user_id"], "camera_changed", str(camera_id), None, client_ip(request))
    return {"status": "success"}
