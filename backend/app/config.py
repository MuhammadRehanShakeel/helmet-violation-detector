"""
config.py - ALL settings for RoadGuard live here.

Want to change a fine, a confidence threshold or a security rule?
Change it in this file (or in backend/.env for secrets). No other file needs editing.
"""
import os
from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default=None, required: bool = False) -> str:
    """Read one value from .env. Stop with a clear message if a required value is missing."""
    value = os.getenv(name, default)
    if required and (value is None or str(value).strip() == ""):
        raise RuntimeError(
            f"Missing setting '{name}' in backend/.env. "
            f"Copy backend/.env.example to backend/.env and fill it in."
        )
    return value


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# 1. Database (from .env) - RoadGuard has its OWN database on your SQL Server
# ---------------------------------------------------------------------------
DB_SERVER = _env("DB_SERVER", required=True)          # e.g. REHAN\VE_SERVER
DB_NAME = _env("DB_NAME", "RoadGuard")
DB_AUTH = _env("DB_AUTH", "windows").lower()          # "windows" or "sql"
DB_USER = _env("DB_USER", "")
DB_PASSWORD = _env("DB_PASSWORD", "")
DB_DRIVER = _env("DB_DRIVER", "ODBC Driver 17 for SQL Server")

# ---------------------------------------------------------------------------
# 2. Login & security
# ---------------------------------------------------------------------------
JWT_SECRET = _env("JWT_SECRET", required=True)        # long random text, from .env
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = _env_int("JWT_EXPIRE_MINUTES", 120)

ROLES = ("admin", "officer", "viewer")
# admin   -> everything, incl. users and cameras
# officer -> analyse media, review violations, issue e-challans
# viewer  -> read-only dashboard; number plates are partly hidden (privacy)

PASSWORD_MIN_LENGTH = 8
LOGIN_MAX_ATTEMPTS = 5                                # wrong passwords before the account locks
LOGIN_LOCK_MINUTES = 15

RATE_LIMIT_LOGIN = (10, 60)                           # (requests, per seconds) per IP
RATE_LIMIT_LIVE = (120, 60)                           # live camera frames per IP
RATE_LIMIT_DEFAULT = (600, 60)

API_HOST = _env("API_HOST", "127.0.0.1")              # 0.0.0.0 to use the phone app on your Wi-Fi
API_PORT = _env_int("API_PORT", 5001)                 # 5001 so it never clashes with the FYP (5000)
CORS_ORIGINS = [o.strip() for o in _env(
    "CORS_ORIGINS", "http://localhost:5174,http://127.0.0.1:5174"
).split(",") if o.strip()]

# ---------------------------------------------------------------------------
# 3. Files
# ---------------------------------------------------------------------------
DATA_DIR = os.path.join(BACKEND_DIR, _env("DATA_DIR", "data"))
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")        # original photos / videos
EVIDENCE_DIR = os.path.join(DATA_DIR, "evidence")     # annotated frames and crops
CHALLAN_DIR = os.path.join(DATA_DIR, "challans")      # PDF e-challans

MAX_IMAGE_MB = 15
MAX_VIDEO_MB = _env_int("MAX_VIDEO_MB", 300)
MAX_VIDEO_SECONDS = 10 * 60
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}

# ---------------------------------------------------------------------------
# 4. AI model (runs offline with ONNX Runtime on the CPU)
# ---------------------------------------------------------------------------
MODEL_PATH = os.path.join(BACKEND_DIR, "models", _env("MODEL_FILE", "roadguard_yolo11n.onnx"))
# Backup model: the standard COCO-pretrained YOLO11n (knows "person" and "motorcycle").
# Some training images label heads but not the motorcyclist, so the main model sometimes finds
# a bare head without the bike around it. Then this model finds the bike + riders instead.
COCO_MODEL_PATH = os.path.join(BACKEND_DIR, "models", "yolo11n_coco.onnx")
USE_BIKE_FALLBACK = True
MODEL_IMAGE_SIZE = 640                                # must match the size used in training
CPU_THREADS = _env_int("CPU_THREADS", 4)

DETECT_CONFIDENCE = 0.30                              # ignore boxes below this score
NMS_IOU = 0.50                                        # overlap above this = same object
LOW_CONFIDENCE = 0.55                                 # violations below this get a "check carefully" flag

# The model's class names can differ between datasets.
# Every name on the right is treated as the role on the left.
CLASS_ALIASES = {
    "motorcyclist": ["motorcyclist", "rider", "motorbike"],
    "helmet": ["helmet", "withhelmet", "with_helmet", "with helmet"],
    "no_helmet": ["nohelmet", "no_helmet", "no-helmet", "withouthelmet", "without_helmet", "without helmet", "head"],
    "plate": ["licenseplate", "license_plate", "license plate", "plate", "numberplate", "number_plate", "number plate"],
}

TRIPLE_RIDING_MIN = 3                                 # this many people on one bike = violation

# Video: we do not need every frame. 5 frames per second is enough for traffic.
VIDEO_SAMPLE_FPS = 5
TRACK_IOU = 0.30                                      # same bike in the next frame if boxes overlap this much
TRACK_MAX_MISSING = 10                                # frames a bike may disappear before its track ends
# CCTV / IP cameras watched in the background
STREAM_FPS = 2                                        # frames analysed per second per camera
MAX_STREAMS = 3                                       # cameras at the same time (CPU limit of a laptop)
SCENE_CUT_DIFF = 40                                   # picture changes this much (0-255) = a cut: start fresh tracks
MIN_VIOLATION_FRAMES = 2                              # a bike must break the rule in >= 2 frames (fewer false alarms)

# ---------------------------------------------------------------------------
# 5. Number plates (Pakistan)
# ---------------------------------------------------------------------------
# Words printed on Pakistani plates that are NOT part of the registration number
PLATE_IGNORE_WORDS = ["PUNJAB", "SINDH", "ISLAMABAD", "BALOCHISTAN", "KPK", "KHYBER",
                      "PAKHTUNKHWA", "GILGIT", "AJK", "PAKISTAN", "GOVT", "ICT"]
PLATE_MIN_CONFIDENCE = 0.75                           # below this the plate is "unreadable" (tuned on the dev plates)

# ---------------------------------------------------------------------------
# 6. Fines (Rs). Punjab rates reported May 2026 - change if the law changes.
# ---------------------------------------------------------------------------
FINES = {
    "NO_HELMET": 2000,
    "TRIPLE_RIDING": 1000,
}
VIOLATION_LABELS = {
    "NO_HELMET": "Riding without a helmet",
    "TRIPLE_RIDING": "More than two people on a motorcycle",
}
CHALLAN_AUTHORITY = _env("CHALLAN_AUTHORITY", "RoadGuard Demo Traffic Unit")   # shown on the PDF
PUBLIC_BASE_URL = _env("PUBLIC_BASE_URL", "http://localhost:5174")             # used in the QR code
