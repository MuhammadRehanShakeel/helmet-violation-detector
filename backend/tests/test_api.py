"""API security: roles, lockout, upload checks, review rules, challans, private evidence."""
import io
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.auth import mask_plate
from app.core.security import create_token, hash_password
from main import app

USERS = {
    1: {"user_id": 1, "full_name": "Admin", "email": "admin@test.pk", "role": "admin", "is_active": True},
    2: {"user_id": 2, "full_name": "Officer", "email": "officer@test.pk", "role": "officer", "is_active": True},
    3: {"user_id": 3, "full_name": "Viewer", "email": "viewer@test.pk", "role": "viewer", "is_active": True},
}


def headers(user_id):
    u = USERS[user_id]
    return {"Authorization": f"Bearer {create_token(u['user_id'], u['email'], u['role'])}"}


@pytest.fixture
def client(fake_db):
    fake_db.on("FROM Users WHERE user_id = ?", lambda p: USERS.get(p[0]))
    return TestClient(app)


def violation_row(**extra):
    row = {"violation_id": 7, "job_id": 1, "camera_id": None, "camera_name": None, "location": None,
           "violation_type": "NO_HELMET", "confidence": 0.9, "low_confidence": False, "riders": 1,
           "no_helmet_count": 1, "plate_text": "LEA-1234", "plate_raw": "LEA 1234", "plate_valid": True,
           "plate_confidence": 0.9, "frame_time": None, "status": "pending", "review_note": None,
           "reviewed_at": None, "reviewed_by_name": None, "created_at": datetime(2026, 10, 1, 9, 30),
           "challan_id": None, "challan_no": None, "evidence_file": "ev_x.jpg", "crop_file": "crop_x.jpg",
           "plate_file": "plate_x.jpg"}
    row.update(extra)
    return row


# --- login ---------------------------------------------------------------
def login_user(**extra):
    row = {"user_id": 2, "full_name": "Officer", "email": "officer@test.pk",
           "password_hash": hash_password("Secret123"), "role": "officer", "is_active": True,
           "failed_logins": 0, "locked_until": None}
    row.update(extra)
    return row


def test_login_ok(client, fake_db):
    fake_db.on("FROM Users WHERE email = ?", login_user())
    r = client.post("/auth/login", json={"email": "officer@test.pk", "password": "Secret123"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "officer"


def test_wrong_password_same_message_as_unknown_email(client, fake_db):
    fake_db.on("FROM Users WHERE email = ?", login_user())
    wrong = client.post("/auth/login", json={"email": "officer@test.pk", "password": "nope1234"})
    fake_db.on("FROM Users WHERE email = ?", None)
    unknown = client.post("/auth/login", json={"email": "ghost@test.pk", "password": "nope1234"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_fifth_wrong_password_locks_account(client, fake_db):
    fake_db.on("FROM Users WHERE email = ?", login_user(failed_logins=4))
    client.post("/auth/login", json={"email": "officer@test.pk", "password": "nope1234"})
    update = fake_db.ran("SET failed_logins = ?, locked_until = ?")[-1]
    assert update[1][1] is not None                       # locked_until was set


def test_locked_account_cannot_login_even_with_right_password(client, fake_db):
    fake_db.on("FROM Users WHERE email = ?", login_user(locked_until=datetime.now() + timedelta(minutes=5)))
    r = client.post("/auth/login", json={"email": "officer@test.pk", "password": "Secret123"})
    assert r.status_code == 423


def test_no_token_no_access(client):
    assert client.get("/violations").status_code == 401
    assert client.get("/violations", headers={"Authorization": "Bearer fake"}).status_code == 401


def test_disabled_user_is_rejected_immediately(client, fake_db):
    fake_db.on("FROM Users WHERE user_id = ?", lambda p: {**USERS[2], "is_active": False})
    assert client.get("/auth/me", headers=headers(2)).status_code == 401


# --- roles ---------------------------------------------------------------
def test_viewer_cannot_upload_review_or_manage(client):
    h = headers(3)
    assert client.post("/jobs", headers=h, files={"file": ("a.jpg", b"x", "image/jpeg")}).status_code == 403
    assert client.put("/violations/7/review", headers=h, json={"decision": "approved"}).status_code == 403
    assert client.get("/users", headers=h).status_code == 403
    assert client.post("/live/start", headers=h, json={}).status_code == 403


def test_officer_cannot_manage_users(client):
    body = {"full_name": "X Y", "email": "x@test.pk", "password": "Secret123", "role": "admin"}
    assert client.post("/users", headers=headers(2), json=body).status_code == 403


def test_admin_cannot_demote_self(client):
    assert client.put("/users/1", headers=headers(1), json={"role": "viewer"}).status_code == 400


def test_viewer_sees_masked_plates(client, fake_db):
    fake_db.on("SELECT COUNT(*) AS n FROM Violations v LEFT JOIN", {"n": 1})
    fake_db.on("OFFSET ? ROWS", lambda p: [violation_row()])
    viewer = client.get("/violations", headers=headers(3)).json()["items"][0]
    officer = client.get("/violations", headers=headers(2)).json()["items"][0]
    assert viewer["plate_text"] == "LEA-**34" and viewer["plate_raw"] is None
    assert officer["plate_text"] == "LEA-1234"


def test_viewer_cannot_open_plate_photo(client):
    assert client.get("/violations/7/image/plate", headers=headers(3)).status_code == 403


def test_evidence_image_needs_login_and_blocks_path_tricks(client, fake_db):
    assert client.get("/violations/7/image/evidence").status_code == 401
    fake_db.on("_file AS f FROM Violations", {"f": "../../main.py"})
    assert client.get("/violations/7/image/evidence", headers=headers(2)).status_code == 404
    assert client.get("/violations/7/image/../../x", headers=headers(2)).status_code in (404, 422)


# --- uploads ---------------------------------------------------------------
def test_fake_image_is_rejected(client):
    r = client.post("/jobs", headers=headers(2), files={"file": ("photo.jpg", b"MZ\x90\x00 not an image", "image/jpeg")})
    assert r.status_code == 400


def test_wrong_extension_is_rejected(client):
    r = client.post("/jobs", headers=headers(2), files={"file": ("virus.exe", b"MZ\x90\x00", "application/octet-stream")})
    assert r.status_code == 400


def test_real_image_is_accepted_and_queued(client, fake_db, monkeypatch):
    import cv2
    import numpy as np
    from app.services import job_queue
    queued = []
    monkeypatch.setattr(job_queue, "enqueue", queued.append)
    ok, jpg = cv2.imencode(".jpg", np.full((120, 160, 3), 200, np.uint8))
    r = client.post("/jobs", headers=headers(2), files={"file": ("road.jpg", io.BytesIO(jpg.tobytes()), "image/jpeg")})
    assert r.status_code == 201 and r.json()["kind"] == "image" and queued == [r.json()["job_id"]]


def test_other_officers_job_is_hidden(client, fake_db):
    fake_db.on("WHERE j.job_id = ?", {"job_id": 5, "user_id": 99})
    assert client.get("/jobs/5", headers=headers(2)).status_code == 404
    assert client.get("/jobs/5", headers=headers(1)).status_code == 200        # admin sees all


# --- review and challans ---------------------------------------------------
def test_cannot_approve_without_a_plate(client, fake_db):
    fake_db.on("WHERE v.violation_id = ?", violation_row(plate_text=None))
    r = client.put("/violations/7/review", headers=headers(2), json={"decision": "approved"})
    assert r.status_code == 400


def test_officer_can_correct_plate_and_it_is_cleaned(client, fake_db):
    fake_db.on("WHERE v.violation_id = ?", violation_row(plate_text=None))
    r = client.put("/violations/7/review", headers=headers(2), json={"decision": "approved", "plate_text": "lea 12 3456"})
    assert r.status_code == 200 and r.json()["plate_text"] == "LEA-3456"
    assert fake_db.ran("INSERT INTO AuditLog")


def test_invalid_corrected_plate_is_refused(client, fake_db):
    fake_db.on("WHERE v.violation_id = ?", violation_row())
    r = client.put("/violations/7/review", headers=headers(2), json={"decision": "approved", "plate_text": "123"})
    assert r.status_code == 400


def test_challan_only_for_approved(client, fake_db):
    fake_db.on("WHERE v.violation_id = ?", violation_row(status="pending"))
    assert client.post("/violations/7/challan", headers=headers(2)).status_code == 400


def test_challan_pdf_is_created(client, fake_db):
    fake_db.on("WHERE v.violation_id = ?", violation_row(status="approved"))
    fake_db.on("SELECT issued_at FROM Challans", {"issued_at": datetime(2026, 10, 2, 10, 0)})
    r = client.post("/violations/7/challan", headers=headers(2))
    assert r.status_code == 201 and r.json()["challan_no"].startswith("RG-")
    import os
    from app import config
    assert os.path.exists(os.path.join(config.CHALLAN_DIR, f"{r.json()['challan_no']}.pdf"))


def test_reviewed_violation_with_challan_is_locked(client, fake_db):
    fake_db.on("WHERE v.violation_id = ?", violation_row(status="approved", challan_id=3, challan_no="RG-1"))
    r = client.put("/violations/7/review", headers=headers(2), json={"decision": "rejected"})
    assert r.status_code == 409


def test_public_verify_shows_only_masked_plate(client, fake_db):
    fake_db.on("WHERE ch.verify_code = ?", {"challan_no": "RG-1", "fine_amount": 2000, "issued_at": datetime.now(),
                                            "violation_type": "NO_HELMET", "plate_text": "LEA-1234"})
    r = client.get("/challans/verify/abcdefghijklmnop")
    assert r.status_code == 200 and r.json()["plate"] == "LEA-**34"
    assert client.get("/challans/verify/x").status_code == 404


def test_security_headers(client):
    r = client.get("/")
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["X-Frame-Options"] == "DENY"


def test_mask_plate():
    assert mask_plate("LEA-1234", "viewer") == "LEA-**34"
    assert mask_plate("LEA-1234", "officer") == "LEA-1234"
    assert mask_plate(None, "viewer") is None
