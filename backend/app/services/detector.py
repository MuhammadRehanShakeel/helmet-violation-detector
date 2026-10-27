"""
detector.py - Runs the trained YOLO11 model with ONNX Runtime (CPU, no GPU needed).

How it works, step by step:
  1. letterbox()   - resize the photo to 640x640 without stretching it (grey borders fill the rest)
  2. the model     - returns 8400 candidate boxes, each with a score for every class
  3. decode()      - keep boxes above DETECT_CONFIDENCE, convert them back to the photo's size
  4. NMS           - when several boxes cover the same object, keep only the best one

The class names are read from the model file itself, then mapped to our 4 roles
(motorcyclist, helmet, no_helmet, plate) using config.CLASS_ALIASES.

Used by: app/services/analyzer.py
"""
import ast
import logging
import os
import threading

import cv2
import numpy as np

from app import config

log = logging.getLogger("detector")


def letterbox(image, size: int):
    """Resize keeping the aspect ratio. Returns the new image, the scale and the padding."""
    h, w = image.shape[:2]
    scale = min(size / h, size / w)
    new_w, new_h = int(round(w * scale)), int(round(h * scale))
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    pad_x, pad_y = (size - new_w) // 2, (size - new_h) // 2
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    canvas[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized
    return canvas, scale, pad_x, pad_y


def role_for(class_name: str):
    """'WithoutHelmet' -> 'no_helmet', 'licenseplate' -> 'plate', unknown -> None."""
    key = class_name.strip().lower()
    for role, names in config.CLASS_ALIASES.items():
        if key in names:
            return role
    return None


def decode(output, scale, pad_x, pad_y, image_w, image_h, names, conf_threshold, iou_threshold):
    """
    Turn the raw model output (1, 4 + classes, N) into a list of detections:
    [{"role", "label", "conf", "box": [x1, y1, x2, y2]}]
    """
    preds = np.squeeze(output, 0).T                      # (N, 4 + classes)
    boxes_xywh, class_scores = preds[:, :4], preds[:, 4:]
    class_ids = class_scores.argmax(axis=1)
    scores = class_scores[np.arange(len(class_ids)), class_ids]
    keep = scores >= conf_threshold
    boxes_xywh, class_ids, scores = boxes_xywh[keep], class_ids[keep], scores[keep]
    if len(scores) == 0:
        return []

    # centre-x, centre-y, width, height  ->  x1, y1, x2, y2 in the ORIGINAL photo
    x1 = (boxes_xywh[:, 0] - boxes_xywh[:, 2] / 2 - pad_x) / scale
    y1 = (boxes_xywh[:, 1] - boxes_xywh[:, 3] / 2 - pad_y) / scale
    x2 = (boxes_xywh[:, 0] + boxes_xywh[:, 2] / 2 - pad_x) / scale
    y2 = (boxes_xywh[:, 1] + boxes_xywh[:, 3] / 2 - pad_y) / scale
    boxes = np.stack([x1.clip(0, image_w), y1.clip(0, image_h), x2.clip(0, image_w), y2.clip(0, image_h)], axis=1)

    detections = []
    for class_id in np.unique(class_ids):                # NMS separately for each class
        idx = np.where(class_ids == class_id)[0]
        rects = [[float(b[0]), float(b[1]), float(b[2] - b[0]), float(b[3] - b[1])] for b in boxes[idx]]
        kept = cv2.dnn.NMSBoxes(rects, scores[idx].astype(float).tolist(), conf_threshold, iou_threshold)
        for k in np.array(kept).flatten():
            i = idx[int(k)]
            label = names.get(int(class_id), str(class_id))
            detections.append({
                "role": role_for(label),
                "label": label,
                "conf": round(float(scores[i]), 3),
                "box": [round(float(v), 1) for v in boxes[i]],
            })
    detections.sort(key=lambda d: d["conf"], reverse=True)
    return detections


class Detector:
    """Loads the ONNX model once and detects objects in BGR images (OpenCV format)."""

    def __init__(self, model_path: str = None):
        self.model_path = model_path or config.MODEL_PATH
        self.session = None
        self.names = {}
        self.input_name = None
        self.size = config.MODEL_IMAGE_SIZE
        self._lock = threading.Lock()

    def is_available(self) -> bool:
        return os.path.exists(self.model_path)

    def load(self):
        if self.session is not None:
            return
        with self._lock:
            if self.session is not None:
                return
            if not self.is_available():
                raise FileNotFoundError(
                    f"Model not found: {self.model_path}. Train it with training/train_roadguard_colab.ipynb "
                    f"and copy the .onnx file into backend/models/ (see backend/models/README.md)."
                )
            import onnxruntime as ort
            options = ort.SessionOptions()
            options.intra_op_num_threads = config.CPU_THREADS
            self.session = ort.InferenceSession(self.model_path, options, providers=["CPUExecutionProvider"])
            meta = self.session.get_modelmeta().custom_metadata_map
            self.names = ast.literal_eval(meta["names"]) if "names" in meta else {}
            if "imgsz" in meta:
                self.size = int(ast.literal_eval(meta["imgsz"])[0])
            self.input_name = self.session.get_inputs()[0].name
            log.info("Model loaded: %s | classes: %s", os.path.basename(self.model_path), self.names)

    def class_roles(self) -> dict:
        self.load()
        return {name: role_for(name) for name in self.names.values()}

    def detect(self, image, conf_threshold: float = None):
        self.load()
        h, w = image.shape[:2]
        canvas, scale, pad_x, pad_y = letterbox(image, self.size)
        blob = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        blob = np.ascontiguousarray(blob.transpose(2, 0, 1)[None])       # (1, 3, 640, 640)
        output = self.session.run(None, {self.input_name: blob})[0]
        return decode(output, scale, pad_x, pad_y, w, h, self.names,
                      conf_threshold or config.DETECT_CONFIDENCE, config.NMS_IOU)


detector = Detector()
coco_detector = Detector(config.COCO_MODEL_PATH)        # backup bike finder (see rules.bikes_from_coco)
