"""
tracker.py - Follows each motorcycle through a video, so one bike = one violation.

Without tracking, a bike visible for 3 seconds (15 analysed frames) would create
15 violations. The tracker matches every bike to the closest bike from the
previous frame (by box overlap, "IoU"), and gives it a stable track id.

For every track we collect "votes" over many frames:
  * in how many frames the rider had no helmet  -> needs MIN_VIOLATION_FRAMES (fewer false alarms)
  * the plate text read in each frame          -> the most common reading wins ("plate voting")
  * the clearest frame                          -> kept as the evidence photo

Used by: app/services/analyzer.py (videos and the live camera)
"""
from collections import Counter

from app import config
from app.services.rules import iou


class Track:
    def __init__(self, track_id, bike, frame_index):
        self.id = track_id
        self.box = bike["box"]
        self.first_frame = frame_index
        self.last_frame = frame_index
        self.missing = 0
        self.frames_seen = 0
        self.max_riders = 0
        self.violation_frames = Counter()       # "NO_HELMET" -> number of frames
        self.best = {}                          # violation type -> best snapshot
        self.plate_votes = Counter()            # "LEA-1234" -> weighted votes
        self.plate_info = {}                    # plate text -> best OCR result for it
        self.reported = set()                   # violation types already saved

    def update(self, bike, frame_index, snapshot=None):
        self.box = bike["box"]
        self.last_frame = frame_index
        self.missing = 0
        self.frames_seen += 1
        self.max_riders = max(self.max_riders, bike.get("riders", 0))
        for v in bike.get("violations", []):
            self.violation_frames[v["type"]] += 1
            best = self.best.get(v["type"])
            if snapshot is not None and (best is None or v["confidence"] > best["confidence"]):
                self.best[v["type"]] = {"confidence": v["confidence"], **snapshot}

    def add_plate(self, reading):
        """Each readable plate counts as one vote, weighted by OCR confidence."""
        if not reading or not reading.get("plate"):
            return
        weight = reading["confidence"] * (2.0 if reading["valid"] else 0.5)
        self.plate_votes[reading["plate"]] += weight
        old = self.plate_info.get(reading["plate"])
        if old is None or reading["confidence"] > old["confidence"]:
            self.plate_info[reading["plate"]] = reading

    def plate(self):
        """The winning plate reading (or None)."""
        if not self.plate_votes:
            return None
        text, _ = self.plate_votes.most_common(1)[0]
        return self.plate_info[text]

    def confirmed_violations(self, finished: bool = True):
        """Violation types seen in enough frames to be trusted."""
        need = config.MIN_VIOLATION_FRAMES
        # a bike that was only visible for 1 frame in total gets the benefit of that one frame,
        # but only once its track has ended (in the live camera it may still be seen again)
        if finished and self.frames_seen < need:
            need = 1
        return [t for t, n in self.violation_frames.items() if n >= need]


class Tracker:
    def __init__(self):
        self.tracks = {}
        self.finished = []
        self._next_id = 1

    def step(self, bikes, frame_index, snapshot_for=None):
        """
        Match this frame's bikes to existing tracks.
        snapshot_for(bike) -> dict with frame info, called only when a bike breaks a rule.
        Returns [(track, bike)] for this frame.
        """
        pairs = []
        candidates = sorted(
            ((iou(t.box, b["box"]), tid, bi) for tid, t in self.tracks.items() for bi, b in enumerate(bikes)),
            reverse=True,
        )
        used_tracks, used_bikes = set(), set()
        for score, tid, bi in candidates:                     # greedy: best overlaps first
            if score < config.TRACK_IOU:
                break
            if tid in used_tracks or bi in used_bikes:
                continue
            used_tracks.add(tid)
            used_bikes.add(bi)
            bike = bikes[bi]
            snap = snapshot_for(bike) if (snapshot_for and bike.get("violations")) else None
            self.tracks[tid].update(bike, frame_index, snap)
            pairs.append((self.tracks[tid], bike))

        for bi, bike in enumerate(bikes):                     # new bikes -> new tracks
            if bi in used_bikes:
                continue
            track = Track(self._next_id, bike, frame_index)
            snap = snapshot_for(bike) if (snapshot_for and bike.get("violations")) else None
            track.update(bike, frame_index, snap)
            self.tracks[self._next_id] = track
            self._next_id += 1
            pairs.append((track, bike))

        for tid in list(self.tracks):                         # bikes that left the picture
            if tid not in used_tracks and self.tracks[tid].last_frame != frame_index:
                self.tracks[tid].missing += 1
                if self.tracks[tid].missing > config.TRACK_MAX_MISSING:
                    self.finished.append(self.tracks.pop(tid))
        return pairs

    def close(self):
        """End of video: every remaining track is finished."""
        self.finished.extend(self.tracks.values())
        self.tracks = {}
        return self.finished

    def total_tracks(self):
        return self._next_id - 1
