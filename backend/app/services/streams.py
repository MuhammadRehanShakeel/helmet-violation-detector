"""
streams.py - Watches CCTV / IP cameras in the background, 24/7.

Each camera with "stream enabled" gets its own background thread:

    open the stream ──► read frames ──► every 1/STREAM_FPS s: analyse (same pipeline as videos)
         ▲                                     │
         └── lost? wait 2, 4, 8 ... 30 s ◄──────┘   (reconnects by itself)

Supported addresses:
  rtsp://user:pass@192.168.1.20:554/stream1   - most CCTV / IP cameras
  http://192.168.1.30:8080/video              - phone with the free "IP Webcam" app (MJPEG)
  demo:demo_traffic.mp4                       - a video in backend/data/demo_streams, played in a loop
                                                like a live camera (for demos and tests)

Passwords inside a camera address are NEVER sent back to the browser (masked as ***).
The latest analysed frame (with boxes) is kept in memory for the "CCTV wall" page.

Used by: app/routes/camera_routes.py, main.py (start_all on startup)
"""
import logging
import os
import re
import threading
import time
from urllib.parse import urlparse

import cv2

from app import config
from app.database import execute_insert_and_get_id, execute_query
from app.services.analyzer import VideoSession
from app.services.events import event_bus
from app.services.storage import save_violation

log = logging.getLogger("streams")
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")   # RTSP over TCP is more reliable
DEMO_DIR = os.path.join(config.DATA_DIR, "demo_streams")
os.makedirs(DEMO_DIR, exist_ok=True)

GREEN, RED, YELLOW = (60, 180, 60), (40, 40, 220), (0, 210, 255)


# ---------------------------------------------------------------------------
# Addresses
# ---------------------------------------------------------------------------
def validate_url(url: str) -> str:
    """Only camera addresses are accepted (no file paths, no other schemes)."""
    url = (url or "").strip()
    if url.startswith("demo:"):
        name = os.path.basename(url[5:])
        if not name or not os.path.isfile(os.path.join(DEMO_DIR, name)):
            raise ValueError(f"Demo video not found. Put it in backend/data/demo_streams/ ({name or 'empty name'}).")
        return f"demo:{name}"
    parsed = urlparse(url)
    if parsed.scheme not in ("rtsp", "rtsps", "http", "https") or not parsed.hostname:
        raise ValueError("Use an rtsp://, http:// or https:// camera address (or demo:<video file>).")
    return url


def mask_url(url):
    """rtsp://admin:secret@10.0.0.5/live -> rtsp://***@10.0.0.5/live"""
    if not url:
        return url
    return re.sub(r"//[^/@]+@", "//***@", url)


def _open(url):
    if url.startswith("demo:"):
        return cv2.VideoCapture(os.path.join(DEMO_DIR, url[5:]))
    params = [cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000, cv2.CAP_PROP_READ_TIMEOUT_MSEC, 10000]
    try:
        return cv2.VideoCapture(url, cv2.CAP_FFMPEG, params)
    except TypeError:                                    # older OpenCV without the params argument
        return cv2.VideoCapture(url, cv2.CAP_FFMPEG)


# ---------------------------------------------------------------------------
# One camera
# ---------------------------------------------------------------------------
class CameraStream(threading.Thread):
    def __init__(self, camera_id, name, url, user_id):
        super().__init__(name=f"camera-{camera_id}", daemon=True)
        self.camera_id = camera_id
        self.camera_name = name
        self.url = url
        self.user_id = user_id
        self.stop_event = threading.Event()
        self.status = "starting"
        self.error = None
        self.job_id = None
        self.session = None
        self.frames = 0
        self.violations = 0
        self.started = time.time()
        self.last_frame_at = None
        self.ms_per_frame = None
        self.snapshot = None                      # latest JPEG with boxes
        self.lock = threading.Lock()

    # -- status shown in the app --
    def info(self):
        return {
            "camera_id": self.camera_id, "name": self.camera_name, "status": self.status, "error": self.error,
            "job_id": self.job_id, "frames_analysed": self.frames, "violations": self.violations,
            "motorcyclists": self.session.tracker.total_tracks() if self.session else 0,
            "running_seconds": round(time.time() - self.started), "ms_per_frame": self.ms_per_frame,
            "last_frame_at": self.last_frame_at, "url": mask_url(self.url),
        }

    def _set_status(self, status, error=None):
        changed = status != self.status
        self.status, self.error = status, error
        if changed:
            event_bus.publish({"type": "stream", "camera_id": self.camera_id, "camera": self.camera_name,
                               "status": status, "error": error}, roles=("admin", "officer"))

    def stop(self):
        self.stop_event.set()

    # -- the thread --
    def run(self):
        self.job_id = execute_insert_and_get_id(
            "INSERT INTO Jobs (user_id, camera_id, kind, original_name, status, stage) OUTPUT INSERTED.job_id "
            "VALUES (?, ?, 'stream', ?, 'running', 'Watching')",
            (self.user_id, self.camera_id, f"{self.camera_name} (CCTV)"[:255]))
        self.session = VideoSession()
        backoff = 2
        try:
            while not self.stop_event.is_set():
                capture = _open(self.url)
                if not capture.isOpened():
                    self._set_status("reconnecting", "Cannot reach the camera")
                    capture.release()
                    self.stop_event.wait(backoff)
                    backoff = min(30, backoff * 2)
                    continue
                backoff = 2
                self._set_status("live")
                self._watch(capture)
                capture.release()
                if not self.stop_event.is_set() and not self.url.startswith("demo:"):
                    self._set_status("reconnecting", "The stream stopped")
                    self.stop_event.wait(backoff)
        except Exception as e:                       # never let one camera crash the server
            log.exception("Camera %s crashed", self.camera_id)
            self._set_status("error", str(e)[:200])
        finally:
            self._finish()

    def _watch(self, capture):
        demo = self.url.startswith("demo:")
        source_fps = capture.get(cv2.CAP_PROP_FPS) or 25
        interval = 1.0 / config.STREAM_FPS
        next_analysis = 0.0
        while not self.stop_event.is_set():
            loop_start = time.time()
            ok, frame = capture.read()
            if not ok:
                if demo:                                 # demo video: start again from the beginning
                    capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                return                                   # real camera: reconnect
            now = time.time()
            if now >= next_analysis:
                next_analysis = now + interval
                self._analyse(frame, now)
            if demo:                                     # play the file at its real speed
                time.sleep(max(0.0, 1.0 / source_fps - (time.time() - loop_start)))

    def _analyse(self, frame, now):
        started = time.time()
        bikes, _ = self.session.feed(frame, round(now - self.started, 1))
        new = self.session.collect(list(self.session.tracker.tracks.values()), finished=False)
        for v in new:
            save_violation(self.job_id, self.camera_id, v, source="cctv")
        self.violations += len(new)
        self.frames += 1
        self.ms_per_frame = int((time.time() - started) * 1000)
        self.last_frame_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        with self.lock:
            self.snapshot = _draw(frame, bikes, self.camera_name)
        if self.frames % 50 == 0:                        # keep the Jobs table roughly up to date
            execute_query("UPDATE Jobs SET motorcyclists = ?, violations = ? WHERE job_id = ?",
                          (self.session.tracker.total_tracks(), self.violations, self.job_id), commit=True)

    def _finish(self):
        try:
            if self.session:
                for v in self.session.finish():
                    save_violation(self.job_id, self.camera_id, v, source="cctv")
                    self.violations += 1
            if self.job_id:
                execute_query(
                    """UPDATE Jobs SET status = 'done', progress = 100, stage = 'Stopped', motorcyclists = ?,
                           violations = ?, seconds_taken = ?, finished_at = SYSDATETIME() WHERE job_id = ?""",
                    (self.session.tracker.total_tracks() if self.session else 0, self.violations,
                     round(time.time() - self.started, 1), self.job_id), commit=True)
        except Exception:
            log.exception("Could not close camera %s", self.camera_id)
        self._set_status("stopped")


def _draw(frame, bikes, title):
    """The picture for the CCTV wall: boxes + camera name + time. Returns JPEG bytes."""
    image = frame.copy()
    scale = max(1, image.shape[1] // 640)
    for bike in bikes:
        colour = RED if bike["status"] == "violation" else GREEN
        x1, y1, x2, y2 = [int(v) for v in bike["box"]]
        cv2.rectangle(image, (x1, y1), (x2, y2), colour, 2 * scale)
        for head in bike["heads"]:
            hx1, hy1, hx2, hy2 = [int(v) for v in head["box"]]
            cv2.rectangle(image, (hx1, hy1), (hx2, hy2), RED if head["role"] == "no_helmet" else GREEN, scale)
        for plate in bike["plates"]:
            px1, py1, px2, py2 = [int(v) for v in plate["box"]]
            cv2.rectangle(image, (px1, py1), (px2, py2), YELLOW, scale)
    label = f"{title}  {time.strftime('%d-%m-%Y %H:%M:%S')}"
    cv2.rectangle(image, (0, 0), (image.shape[1], 28 * scale), (20, 20, 20), -1)
    cv2.putText(image, label, (8, 20 * scale), cv2.FONT_HERSHEY_SIMPLEX, 0.6 * scale, (255, 255, 255), scale,
                cv2.LINE_AA)
    height = 540                                         # smaller pictures = faster CCTV wall
    if image.shape[0] > height:
        image = cv2.resize(image, (int(image.shape[1] * height / image.shape[0]), height))
    ok, jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 75])
    return jpeg.tobytes() if ok else None


# ---------------------------------------------------------------------------
# All cameras
# ---------------------------------------------------------------------------
class StreamManager:
    def __init__(self):
        self.streams = {}
        self.lock = threading.Lock()

    def start(self, camera_id, name, url, user_id):
        with self.lock:
            running = self.streams.get(camera_id)
            if running and running.is_alive():
                return running
            if sum(1 for s in self.streams.values() if s.is_alive()) >= config.MAX_STREAMS:
                raise RuntimeError(f"At most {config.MAX_STREAMS} cameras can be watched at the same time on this PC.")
            stream = CameraStream(camera_id, name, url, user_id)
            self.streams[camera_id] = stream
            stream.start()
            log.info("Watching camera %s (%s)", camera_id, mask_url(url))
            return stream

    def stop(self, camera_id, wait=True):
        with self.lock:
            stream = self.streams.pop(camera_id, None)
        if stream:
            stream.stop()
            if wait:
                stream.join(timeout=15)

    def stop_all(self):
        for camera_id in list(self.streams):
            self.stop(camera_id)

    def status(self):
        with self.lock:
            return {cid: s.info() for cid, s in self.streams.items()}

    def snapshot(self, camera_id):
        stream = self.streams.get(camera_id)
        if not stream:
            return None
        with stream.lock:
            return stream.snapshot

    def start_enabled(self):
        """On server start: resume every camera that has 'stream enabled'."""
        try:
            admin = execute_query("SELECT TOP 1 user_id FROM Users WHERE role = 'admin' ORDER BY user_id", fetch_one=True)
            rows = execute_query("SELECT camera_id, name, stream_url FROM Cameras WHERE stream_enabled = 1 "
                                 "AND is_active = 1 AND stream_url IS NOT NULL", fetch_all=True) or []
            for row in rows:
                try:
                    self.start(row["camera_id"], row["name"], row["stream_url"], admin["user_id"] if admin else 1)
                except Exception:
                    log.exception("Could not start camera %s", row["camera_id"])
        except Exception:
            log.exception("Could not resume camera streams (has init_db.py been run after the update?)")


stream_manager = StreamManager()
