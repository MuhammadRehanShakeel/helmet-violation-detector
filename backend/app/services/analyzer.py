"""
analyzer.py - The full pipeline: photo/video in, violations out.

    frame ──► detector (YOLO11, ONNX) ──► rules (who breaks which rule)
                                           │
                     videos only: tracker ◄┘  (one bike = one violation, plate voting)
                                           │
                     plate OCR + clean-up ◄┘  (only for offenders, saves CPU time)
                                           │
                     evidence photos  ◄────┘  (bystanders blurred)

Every function returns plain dicts and numpy images. Saving to the database
and disk happens in app/services/job_queue.py, so this file stays easy to test.
"""
import logging
import time

import cv2

from app import config
from app.services.detector import coco_detector as default_helper
from app.services.detector import detector as default_detector
from app.services.evidence import make_evidence
from app.services.plates import crop_box, plate_reader as default_reader
from app.services.rules import analyse_detections, bikes_from_coco, has_orphan_heads
from app.services.tracker import Tracker

log = logging.getLogger("analyzer")
MAX_PLATE_READS_PER_TRACK = 8


def _violation(vtype, confidence, bike, plate, frame_time, images):
    evidence, crop, plate_crop = images
    return {
        "type": vtype,
        "confidence": confidence,
        "low_confidence": confidence < config.LOW_CONFIDENCE,
        "riders": bike.get("riders", 0),
        "no_helmet_count": bike.get("no_helmet_count", 0),
        "plate": plate,
        "frame_time": frame_time,
        "evidence": evidence,
        "crop": crop,
        "plate_crop": plate_crop,
    }


def detect_frame(frame, detector, helper=None):
    """
    Main model first. Only if it found a head with no motorcyclist around it,
    ask the backup COCO model where the bikes and riders are (costs ~70 ms, only then).
    """
    detections = detector.detect(frame)
    if helper is not None and config.USE_BIKE_FALLBACK and has_orphan_heads(detections) \
            and helper.is_available():
        existing = [d for d in detections if d["role"] == "motorcyclist"]
        detections += bikes_from_coco(helper.detect(frame), existing)
    return detections


def read_bike_plate(frame, bike, reader):
    if not bike["plates"]:
        return None
    return reader.read(crop_box(frame, bike["plates"][0]["box"], pad=0.1))


def public_bike(bike):
    """A bike without numpy data, safe to send as JSON (live camera overlay)."""
    return {
        "box": bike["box"], "conf": bike["conf"], "status": bike["status"],
        "riders": bike["riders"], "violations": bike["violations"],
        "heads": [{"role": h["role"], "box": h["box"], "conf": h["conf"]} for h in bike["heads"]],
        "plates": [{"box": p["box"], "conf": p["conf"]} for p in bike["plates"]],
    }


# ---------------------------------------------------------------------------
# Photos
# ---------------------------------------------------------------------------
def analyse_image(image, detector=None, reader=None, helper=None):
    """One photo -> {"bikes": [...], "violations": [...]}"""
    if detector is None:
        detector, helper = default_detector, default_helper
    reader = reader or default_reader
    bikes = analyse_detections(detect_frame(image, detector, helper))
    violations = []
    for i, bike in enumerate(bikes):
        if not bike["violations"]:
            continue
        plate = read_bike_plate(image, bike, reader)
        for v in bike["violations"]:
            images = make_evidence(image, bikes, i, v["type"], plate and plate["plate"])
            violations.append(_violation(v["type"], v["confidence"], bike, plate, None, images))
    return {"bikes": bikes, "violations": violations}


# ---------------------------------------------------------------------------
# Videos
# ---------------------------------------------------------------------------
class VideoSession:
    """
    Analyses a stream of frames (a video file or the live camera) with tracking.
    feed(frame, time) for each frame, then finish() to get the violations.
    """

    def __init__(self, detector=None, reader=None, helper=None):
        if detector is None:
            detector, helper = default_detector, default_helper
        self.detector = detector
        self.helper = helper
        self.reader = reader or default_reader
        self.tracker = Tracker()
        self.frame_index = 0
        self.plate_reads = {}
        self.previous_thumb = None
        self.scene_cuts = 0

    def _is_scene_cut(self, frame):
        """Edited videos jump between places. After a cut, a bike at the same spot is a NEW bike."""
        thumb = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (64, 36)).astype("int16")
        cut = self.previous_thumb is not None and \
            float(abs(thumb - self.previous_thumb).mean()) > config.SCENE_CUT_DIFF
        self.previous_thumb = thumb
        return cut

    def feed(self, frame, frame_time):
        if self._is_scene_cut(frame):
            self.tracker.close()                      # end every track; their violations are kept
            self.scene_cuts += 1
        bikes = analyse_detections(detect_frame(frame, self.detector, self.helper))

        def snapshot(bike):
            idx = bikes.index(bike)
            return {"frame": frame, "bikes": bikes, "index": idx, "time": frame_time, "bike": bike}

        pairs = self.tracker.step(bikes, self.frame_index, snapshot)
        for track, bike in pairs:
            if not track.violation_frames or not bike["plates"]:
                continue
            reads = self.plate_reads.get(track.id, 0)
            if reads < MAX_PLATE_READS_PER_TRACK:
                track.add_plate(read_bike_plate(frame, bike, self.reader))
                self.plate_reads[track.id] = reads + 1
        self.frame_index += 1
        return bikes, pairs

    def collect(self, tracks, finished=True):
        """Turn tracks into violations (each type reported once per bike)."""
        results = []
        for track in tracks:
            plate = track.plate()
            for vtype in track.confirmed_violations(finished):
                if vtype in track.reported or vtype not in track.best:
                    continue
                track.reported.add(vtype)
                snap = track.best[vtype]
                plate_text = plate["plate"] if plate else None
                images = make_evidence(snap["frame"], snap["bikes"], snap["index"], vtype, plate_text)
                bike = {**snap["bike"], "riders": max(snap["bike"].get("riders", 0),
                                                       track.max_riders if vtype == "TRIPLE_RIDING" else 0)}
                results.append(_violation(vtype, snap["confidence"], bike, plate, snap["time"], images))
        return results

    def finish(self):
        return self.collect(self.tracker.close())


def analyse_video(path, progress=None, detector=None, reader=None):
    """
    Analyse a video file, sampling VIDEO_SAMPLE_FPS frames per second.
    progress(percent, stage_text) is called now and then.
    Returns {"violations", "motorcyclists", "frames", "seconds"}
    """
    capture = cv2.VideoCapture(path)
    if not capture.isOpened():
        raise ValueError("This video could not be opened.")
    fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    step = max(1, round(fps / config.VIDEO_SAMPLE_FPS))
    session = VideoSession(detector, reader)
    started, index, analysed = time.time(), 0, 0
    try:
        while True:
            ok = capture.grab()                       # grab() is fast: skipped frames are not decoded
            if not ok:
                break
            if index % step == 0:
                ok, frame = capture.retrieve()
                if not ok:
                    break
                session.feed(frame, round(index / fps, 2))
                analysed += 1
                if progress and analysed % 10 == 0 and total:
                    progress(min(95, int(index * 100 / total)), f"Analysing frame {index} of {total}")
            index += 1
    finally:
        capture.release()
    if progress:
        progress(96, "Reading number plates and saving evidence")
    violations = session.finish()
    return {
        "violations": violations,
        "motorcyclists": session.tracker.total_tracks(),
        "frames": analysed,
        "seconds": round(time.time() - started, 1),
    }
