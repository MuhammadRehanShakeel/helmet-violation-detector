"""
benchmark_speed.py - How fast is RoadGuard on THIS computer's CPU?

Measures:
  * detector    - YOLO11n ONNX, one 640x640 image (the model runs once per analysed frame)
  * plate OCR   - RapidOCR on one plate crop (only runs for offending bikes)
  * video speed - how many seconds of 1080p video we can analyse per second at 5 frames/second

Run:  backend\\venv\\Scripts\\python.exe evaluation\\benchmark_speed.py [path\\to\\model.onnx]
"""
import json
import os
import platform
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))
os.environ.setdefault("DB_SERVER", "eval")
os.environ.setdefault("JWT_SECRET", "eval-only-secret")

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from app import config  # noqa: E402
from app.services.detector import Detector  # noqa: E402
from app.services.plates import PlateReader  # noqa: E402


def timed(fn, runs):
    fn()                                   # warm-up (first run loads things)
    start = time.perf_counter()
    for _ in range(runs):
        fn()
    return (time.perf_counter() - start) / runs * 1000


def main():
    model_path = sys.argv[1] if len(sys.argv) > 1 else config.MODEL_PATH
    detector = Detector(model_path)
    frame = (np.random.rand(1080, 1920, 3) * 255).astype(np.uint8)
    detect_ms = timed(lambda: detector.detect(frame), 20)

    plates = os.path.join(HERE, "data", "synthetic_plates_test")
    crop = cv2.imread(os.path.join(plates, sorted(f for f in os.listdir(plates) if f.endswith(".jpg"))[150]))
    reader = PlateReader()
    ocr_ms = timed(lambda: reader.ocr_text(crop), 10)

    frame_ms = detect_ms + 0.3 * ocr_ms     # assume ~1 in 3 frames has an offender's plate to read
    result = {
        "cpu": platform.processor() or platform.machine(),
        "cpu_threads_used": config.CPU_THREADS,
        "logical_cpus": os.cpu_count(),
        "detector_ms_per_frame": round(detect_ms, 1),
        "plate_ocr_ms": round(ocr_ms, 1),
        "frames_per_second": round(1000 / frame_ms, 1),
        "video_seconds_per_second_at_5fps": round(1000 / frame_ms / config.VIDEO_SAMPLE_FPS, 2),
        "model_file_mb": round(os.path.getsize(model_path) / 1e6, 1),
    }
    print(json.dumps(result, indent=2))
    name = "speed_" + ("this_pc" if len(sys.argv) < 3 else sys.argv[2]) + ".json"
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    with open(os.path.join(HERE, "results", name), "w") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    main()
