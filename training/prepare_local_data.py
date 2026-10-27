"""
prepare_local_data.py - Turn your own traffic videos into a labelling job (with AI pre-labels).

Why: the model learned from other countries' traffic. A few hundred frames from YOUR roads
(Rawalpindi / Islamabad) make it much better there. Drawing every box by hand is slow, so this
script lets the current model draw them first - you only fix its mistakes.

    1. put your videos in training/local_videos/          (phone videos are fine, 1-2 min each)
    2. run:  backend\\venv\\Scripts\\python.exe training\\prepare_local_data.py
    3. upload training/local_dataset/ to a new Roboflow project
       (Roboflow -> New project -> Object detection -> Upload -> choose the folder; it reads the
        YOLO labels + data.yaml automatically)
    4. in Roboflow: check every image, fix / add / delete boxes, then "Generate" a version
    5. put that project in the Colab notebook (LOCAL_PROJECT) and Run all -> new model

Frames are taken every 1 second and nearly identical frames are skipped, so a 2-minute video
gives about 60-100 useful images.
"""
import argparse
import os
import sys

import cv2

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "backend"))
os.environ.setdefault("DB_SERVER", "local")
os.environ.setdefault("JWT_SECRET", "local-tool-only")

from app.services.detector import Detector  # noqa: E402

CLASSES = ["motorcyclist", "helmet", "no_helmet", "plate"]       # same order as the training notebook
VIDEO_TYPES = (".mp4", ".mov", ".avi", ".mkv", ".3gp", ".webm")


def frames(path, every_seconds, min_change):
    capture = cv2.VideoCapture(path)
    fps = capture.get(cv2.CAP_PROP_FPS) or 30
    step = max(1, int(round(fps * every_seconds)))
    index, previous = 0, None
    while True:
        ok = capture.grab()
        if not ok:
            break
        if index % step == 0:
            ok, frame = capture.retrieve()
            if ok:
                small = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (64, 36)).astype("int16")
                if previous is None or abs(small - previous).mean() >= min_change:   # skip near-duplicates
                    previous = small
                    yield index, frame
        index += 1
    capture.release()


def yolo_line(class_id, box, width, height):
    x1, y1, x2, y2 = box
    return (f"{class_id} {(x1 + x2) / 2 / width:.6f} {(y1 + y2) / 2 / height:.6f} "
            f"{(x2 - x1) / width:.6f} {(y2 - y1) / height:.6f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--videos", default=os.path.join(HERE, "local_videos"))
    parser.add_argument("--out", default=os.path.join(HERE, "local_dataset"))
    parser.add_argument("--every", type=float, default=1.0, help="seconds between frames")
    parser.add_argument("--min-change", type=float, default=6.0, help="skip frames that barely changed")
    parser.add_argument("--conf", type=float, default=0.35, help="only pre-label boxes above this confidence")
    args = parser.parse_args()

    videos = sorted(f for f in os.listdir(args.videos) if f.lower().endswith(VIDEO_TYPES)) \
        if os.path.isdir(args.videos) else []
    if not videos:
        os.makedirs(args.videos, exist_ok=True)
        print(f"Put your traffic videos in {args.videos} and run this again.")
        return

    images_dir = os.path.join(args.out, "images")
    labels_dir = os.path.join(args.out, "labels")
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(labels_dir, exist_ok=True)
    detector = Detector()
    total, boxes = 0, {c: 0 for c in CLASSES}
    for video in videos:
        stem = os.path.splitext(video)[0].replace(" ", "_")
        count = 0
        for index, frame in frames(os.path.join(args.videos, video), args.every, args.min_change):
            name = f"{stem}_{index:06d}"
            cv2.imwrite(os.path.join(images_dir, name + ".jpg"), frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
            h, w = frame.shape[:2]
            lines = []
            for d in detector.detect(frame, args.conf):
                if d["role"] in CLASSES:
                    lines.append(yolo_line(CLASSES.index(d["role"]), d["box"], w, h))
                    boxes[d["role"]] += 1
            with open(os.path.join(labels_dir, name + ".txt"), "w") as f:
                f.write("\n".join(lines))
            count += 1
        print(f"{video}: {count} frames")
        total += count
    with open(os.path.join(args.out, "data.yaml"), "w") as f:
        f.write("names:\n" + "".join(f"  {i}: {c}\n" for i, c in enumerate(CLASSES)))
    print(f"\n{total} frames with pre-labels in {args.out}")
    print("Boxes drawn by the AI:", boxes)
    print("Next: upload this folder to a new Roboflow project and FIX the boxes (see training/README.md).")


if __name__ == "__main__":
    main()
