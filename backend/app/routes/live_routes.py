"""
live_routes.py - Use a phone or webcam as a traffic camera.

  POST /live/start               (officer) {camera_id}       -> {job_id}
  POST /live/{job_id}/frame      (officer) multipart "frame" (JPEG)  -> boxes to draw + new violations
  POST /live/{job_id}/stop       (officer)

The browser / Android app sends about one frame per second (rate limited).
"""
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app import config
from app.core.auth import OFFICER
from app.core.security import enforce_rate_limit
from app.routes.camera_routes import get_camera_or_404
from app.services import live
from app.services.detector import detector
from app.services.storage import decode_image_bytes

router = APIRouter(prefix="/live", tags=["Live camera"])


class LiveStart(BaseModel):
    camera_id: Optional[int] = None


@router.post("/start", status_code=201)
def start_live(body: LiveStart, current_user: dict = Depends(OFFICER)):
    get_camera_or_404(body.camera_id)
    if not detector.is_available():
        raise HTTPException(503, "The AI model file is missing. See backend/models/README.md.")
    return {"job_id": live.start(current_user["user_id"], body.camera_id)}


@router.post("/{job_id}/frame")
async def live_frame(job_id: int, request: Request, frame: UploadFile = File(...),
                     current_user: dict = Depends(OFFICER)):
    enforce_rate_limit(request, "live", config.RATE_LIMIT_LIVE)
    session = live.get(job_id, current_user["user_id"])
    if session is None:
        raise HTTPException(404, "This live session has ended. Start a new one.")
    data = await frame.read(config.MAX_IMAGE_MB * 1024 * 1024 + 1)
    image = decode_image_bytes(data)
    from starlette.concurrency import run_in_threadpool        # keep the server responsive
    result = await run_in_threadpool(live.process_frame, session, image)
    result["width"], result["height"] = image.shape[1], image.shape[0]
    return result


@router.post("/{job_id}/stop")
def stop_live(job_id: int, current_user: dict = Depends(OFFICER)):
    session = live.get(job_id, current_user["user_id"])
    if session is None:
        raise HTTPException(404, "This live session has already ended.")
    return {"violations": live.stop(session)}
