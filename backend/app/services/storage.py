"""
storage.py - Saves uploads and evidence images safely, and stores violations in SQL Server.

Security rules for files:
  * uploaded files get a RANDOM name (the user's file name is never used on disk)
  * the file type is checked from its first bytes ("magic numbers"), not just the extension
  * the file must really open as an image / video, and size + length limits apply
  * evidence images are NOT public: they are only served to logged-in users (see routes)

Used by: app/routes/job_routes.py, app/routes/live_routes.py, app/services/job_queue.py
"""
import os
import secrets

import cv2
import numpy as np
from fastapi import HTTPException, UploadFile

from app import config
from app.database import execute_insert_and_get_id, execute_query
from app.services.events import event_bus

for folder in (config.UPLOAD_DIR, config.EVIDENCE_DIR, config.CHALLAN_DIR):
    os.makedirs(folder, exist_ok=True)

CHUNK = 1024 * 1024


def detect_kind(head: bytes):
    """Look at the first bytes of a file. Returns 'image', 'video' or None."""
    if head[:3] == b"\xff\xd8\xff" or head[:8] == b"\x89PNG\r\n\x1a\n" or (head[:4] == b"RIFF" and head[8:12] == b"WEBP"):
        return "image"
    if head[4:8] == b"ftyp" or head[:4] == b"\x1a\x45\xdf\xa3" or (head[:4] == b"RIFF" and head[8:12] == b"AVI "):
        return "video"
    return None


def save_upload(file: UploadFile):
    """
    Save an uploaded photo or video. Returns (kind, path).
    Raises a clear 400 error for anything unsafe or unsupported.
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in config.IMAGE_EXTENSIONS | config.VIDEO_EXTENSIONS:
        raise HTTPException(400, "Please upload a photo (jpg, png, webp) or a video (mp4, mov, avi, mkv, webm).")

    head = file.file.read(16)
    kind = detect_kind(head)
    expected = "image" if ext in config.IMAGE_EXTENSIONS else "video"
    if kind != expected:
        raise HTTPException(400, "This file is not a real photo or video (its content does not match its name).")

    limit = (config.MAX_IMAGE_MB if kind == "image" else config.MAX_VIDEO_MB) * CHUNK
    path = os.path.join(config.UPLOAD_DIR, f"{secrets.token_hex(16)}{ext}")
    size = len(head)
    with open(path, "wb") as out:
        out.write(head)
        while True:
            chunk = file.file.read(CHUNK)
            if not chunk:
                break
            size += len(chunk)
            if size > limit:
                out.close()
                os.remove(path)
                raise HTTPException(413, f"File too large. The limit is {limit // CHUNK} MB.")
            out.write(chunk)

    try:
        check_media(path, kind)
    except HTTPException:
        os.remove(path)
        raise
    return kind, path


def check_media(path: str, kind: str):
    """The file must really open, and videos must not be too long."""
    if kind == "image":
        image = cv2.imread(path)
        if image is None or min(image.shape[:2]) < 32:
            raise HTTPException(400, "This photo could not be read.")
        return
    capture = cv2.VideoCapture(path)
    try:
        if not capture.isOpened():
            raise HTTPException(400, "This video could not be opened.")
        fps = capture.get(cv2.CAP_PROP_FPS) or 25
        frames = capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        if frames / fps > config.MAX_VIDEO_SECONDS:
            raise HTTPException(400, f"Videos can be at most {config.MAX_VIDEO_SECONDS // 60} minutes long.")
    finally:
        capture.release()


def decode_image_bytes(data: bytes):
    """For the live camera: JPEG bytes -> OpenCV image (or 400)."""
    if detect_kind(data[:16]) != "image" or len(data) > config.MAX_IMAGE_MB * CHUNK:
        raise HTTPException(400, "Send a JPEG or PNG frame.")
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(400, "This frame could not be read.")
    return image


def save_image(image, prefix: str):
    """Save an evidence image with a random name. Returns the file name (not the full path)."""
    if image is None or image.size == 0:
        return None
    name = f"{prefix}_{secrets.token_hex(12)}.jpg"
    cv2.imwrite(os.path.join(config.EVIDENCE_DIR, name), image, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return name


def save_violation(job_id: int, camera_id, v: dict, source: str = "upload") -> int:
    """Store one violation (and its 3 images), tell every open browser. Returns the new violation_id."""
    plate = v.get("plate") or {}
    violation_id = execute_insert_and_get_id(
        """INSERT INTO Violations (job_id, camera_id, violation_type, confidence, low_confidence, riders,
               no_helmet_count, plate_text, plate_raw, plate_valid, plate_confidence, frame_time,
               evidence_file, crop_file, plate_file)
           OUTPUT INSERTED.violation_id
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (job_id, camera_id, v["type"], v["confidence"], 1 if v["low_confidence"] else 0, v["riders"],
         v["no_helmet_count"], plate.get("plate"), plate.get("raw"), 1 if plate.get("valid") else 0,
         plate.get("confidence"), v.get("frame_time"),
         save_image(v["evidence"], "ev"), save_image(v["crop"], "crop"), save_image(v.get("plate_crop"), "plate")),
    )
    camera = execute_query("SELECT name FROM Cameras WHERE camera_id = ?", (camera_id,), fetch_one=True) \
        if camera_id else None
    event_bus.publish({
        "type": "violation", "violation_id": violation_id, "violation_type": v["type"],
        "label": config.VIOLATION_LABELS.get(v["type"], v["type"]), "confidence": v["confidence"],
        "camera": camera["name"] if camera else "Uploaded media", "plate": plate.get("plate"),
        "source": source, "low_confidence": bool(v["low_confidence"]),
    })
    return violation_id
