"""
main.py - Starts the RoadGuard API.

Run:  venv\\Scripts\\python.exe main.py      (or double-click start_project.bat)
API docs (try every endpoint): http://localhost:5001/docs
"""
import logging
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.exceptions import HTTPException  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from app import config  # noqa: E402
from app.core.security import enforce_rate_limit  # noqa: E402

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler("logs/backend.log", encoding="utf-8")],
)
log = logging.getLogger("main")

app = FastAPI(
    title="RoadGuard API",
    description="Helmet and number-plate violation detection: YOLO11 (ONNX, CPU) + plate OCR + e-challans.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,          # only our own frontend, never "*"
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT"],          # (no DELETE route exists)
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_layer(request: Request, call_next):
    """General rate limit + safe browser headers on every response."""
    try:
        enforce_rate_limit(request, "all", config.RATE_LIMIT_DEFAULT)
    except HTTPException as e:
        return JSONResponse({"detail": e.detail}, status_code=429)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
    return response


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    """Never show Python errors to users; the details go to logs/backend.log."""
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Something went wrong on the server. Please try again."}, status_code=500)


from app.routes import (auth_routes, camera_routes, citizen_routes, event_routes, job_routes,  # noqa: E402
                        live_routes, report_routes, stats_routes, violation_routes)

for module in (auth_routes, camera_routes, job_routes, violation_routes, stats_routes, live_routes,
               event_routes, citizen_routes, report_routes):
    app.include_router(module.router)


@app.on_event("startup")
def on_startup():
    from app.database import execute_query
    from app.services.detector import detector
    from app.services.job_queue import start_worker
    try:
        execute_query("SELECT 1 AS ok", fetch_one=True)
        log.info("[OK] Connected to SQL Server (%s / %s)", config.DB_SERVER, config.DB_NAME)
    except Exception as e:
        log.error("[ERROR] Database problem: %s  ->  run scripts\\init_db.py first", e)
    if detector.is_available():
        detector.load()
    else:
        log.warning("[!] AI model missing: %s (see backend/models/README.md)", config.MODEL_PATH)
    start_worker()
    from app.services.streams import stream_manager
    stream_manager.start_enabled()                      # resume CCTV cameras that were being watched


@app.on_event("shutdown")
def on_shutdown():
    from app.services.streams import stream_manager
    stream_manager.stop_all()


@app.get("/")
def root():
    return {"api": "RoadGuard", "status": "online", "version": app.version, "docs": "/docs"}


@app.get("/health")
def health():
    from app.database import execute_query
    from app.services.detector import detector
    try:
        execute_query("SELECT 1 AS ok", fetch_one=True)
        db = "ok"
    except Exception:
        db = "down"
    model = "ok" if detector.is_available() else "missing"
    return {"status": "healthy" if db == "ok" and model == "ok" else "degraded", "database": db, "model": model,
            "classes": list(detector.names.values()) if detector.session else None}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.API_HOST, port=config.API_PORT, reload=False)
