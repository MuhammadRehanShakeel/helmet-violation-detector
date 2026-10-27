"""
Test setup: the tests run WITHOUT SQL Server and WITHOUT the trained model.
  * a fake .env is set here
  * pyodbc is replaced by a dummy (the real driver is only needed on the PC)
  * `fake_db` lets a test decide what each SQL query returns
  * FakeDetector / FakeReader return boxes and plates we choose
"""
import os
import sys
import tempfile
import types

os.environ.setdefault("DB_SERVER", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-that-is-long-enough-for-hs256")
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="roadguard_test_"))
sys.modules.setdefault("pyodbc", types.SimpleNamespace(connect=lambda *a, **k: None))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np  # noqa: E402
import pytest  # noqa: E402


class FakeDB:
    """Answers SQL queries with rules: [(text_inside_query, answer_or_function)]."""

    def __init__(self):
        self.rules = []
        self.calls = []

    def on(self, fragment, answer):
        self.rules.insert(0, (fragment, answer))       # newest rule wins

    def __call__(self, query, params=None, fetch_one=False, fetch_all=False, commit=False):
        self.calls.append((query, params))
        for fragment, answer in self.rules:
            if fragment in query:
                return answer(params) if callable(answer) else answer
        return [] if fetch_all else (None if fetch_one else True)

    def ran(self, fragment):
        return [c for c in self.calls if fragment in c[0]]


@pytest.fixture
def fake_db(monkeypatch):
    db = FakeDB()
    ids = iter(range(100, 10_000))
    import app.database
    monkeypatch.setattr(app.database, "execute_query", db)
    monkeypatch.setattr(app.database, "execute_insert_and_get_id", lambda q, p=None: (db.calls.append((q, p)), next(ids))[1])
    for name in list(sys.modules):
        module = sys.modules[name]
        if name.startswith("app.") and hasattr(module, "execute_query"):
            monkeypatch.setattr(module, "execute_query", db, raising=False)
        if name.startswith("app.") and hasattr(module, "execute_insert_and_get_id"):
            monkeypatch.setattr(module, "execute_insert_and_get_id", app.database.execute_insert_and_get_id,
                                raising=False)
    return db


def det(role, box, conf=0.9):
    return {"role": role, "label": role, "conf": conf, "box": list(box)}


class FakeDetector:
    """Returns the same detections (or a list per call) instead of running the model."""

    def __init__(self, frames):
        self.frames = frames if frames and isinstance(frames[0], list) else [frames]
        self.calls = 0

    def is_available(self):
        return True

    def detect(self, image, conf_threshold=None):
        result = self.frames[min(self.calls, len(self.frames) - 1)]
        self.calls += 1
        return [dict(d) for d in result]


class FakeReader:
    def __init__(self, plate="LEA-1234", valid=True, confidence=0.9):
        self.answer = {"plate": plate, "valid": valid, "raw": plate or "", "confidence": confidence}
        self.calls = 0

    def read(self, crop):
        self.calls += 1
        return dict(self.answer)


@pytest.fixture
def blank_frame():
    frame = np.full((480, 640, 3), 128, dtype=np.uint8)
    frame[::8, :] = 30                                  # some texture so blurring changes pixels
    return frame
