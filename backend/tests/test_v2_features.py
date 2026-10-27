"""v2 features: sessions, access requests, citizen portal, appeals, reports, camera streams, live events."""
import os
import time
from datetime import datetime

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import config
from app.core.security import create_token, hash_password
from main import app
from tests.conftest import FakeDetector, FakeReader, det

USERS = {
    1: {"user_id": 1, "full_name": "Admin", "email": "admin@test.pk", "role": "admin", "is_active": True,
        "must_change_password": False, "token_version": 0},
    2: {"user_id": 2, "full_name": "Officer", "email": "officer@test.pk", "role": "officer", "is_active": True,
        "must_change_password": False, "token_version": 3},
}


def headers(user_id, tv=None):
    u = USERS[user_id]
    return {"Authorization": f"Bearer {create_token(u['user_id'], u['email'], u['role'], u['token_version'] if tv is None else tv)}"}


@pytest.fixture
def client(fake_db):
    fake_db.on("FROM Users WHERE user_id = ?", lambda p: dict(USERS[p[0]]) if p and p[0] in USERS else None)
    return TestClient(app)


# --- sessions --------------------------------------------------------------
def test_old_token_stops_working_after_password_change(client):
    assert client.get("/auth/me", headers=headers(2)).status_code == 200
    assert client.get("/auth/me", headers=headers(2, tv=2)).status_code == 401      # made before the change


def test_temporary_password_must_be_changed_first(client, fake_db):
    fake_db.on("FROM Users WHERE user_id = ?", lambda p: {**USERS[2], "must_change_password": True})
    assert client.get("/violations", headers=headers(2)).status_code == 403
    assert client.get("/auth/me", headers=headers(2)).status_code == 200


def test_change_password_returns_new_session(client, fake_db):
    fake_db.on("SELECT password_hash FROM Users", {"password_hash": hash_password("OldPass123")})
    fake_db.on("role, must_change_password, token_version FROM Users", {**USERS[2], "token_version": 4})
    r = client.post("/auth/change-password", headers=headers(2),
                    json={"old_password": "OldPass123", "new_password": "NewPass456"})
    assert r.status_code == 200 and r.json()["access_token"]
    assert fake_db.ran("token_version = token_version + 1")
    same = client.post("/auth/change-password", headers=headers(2),
                       json={"old_password": "OldPass123", "new_password": "OldPass123"})
    assert same.status_code == 400


def test_admin_reset_gives_temporary_password(client, fake_db):
    fake_db.on("SELECT email FROM Users WHERE user_id = ?", {"email": "officer@test.pk"})
    r = client.post("/users/2/reset-password", headers=headers(1))
    assert r.status_code == 200 and r.json()["temporary_password"].startswith("Rg-")
    assert client.post("/users/1/reset-password", headers=headers(1)).status_code == 400   # not yourself
    assert client.post("/users/1/reset-password", headers=headers(2)).status_code == 403   # officers cannot


# --- access requests -------------------------------------------------------
def test_access_request_same_answer_for_existing_email(client, fake_db):
    body = {"full_name": "New Officer", "email": "new@test.pk", "requested_role": "officer"}
    assert client.post("/access-requests", json=body).json() == {"status": "received"}
    fake_db.on("FROM Users WHERE email = ?", {"x": 1})
    assert client.post("/access-requests", json={**body, "email": "admin@test.pk"}).json() == {"status": "received"}
    assert len(fake_db.ran("INSERT INTO AccessRequests")) == 1           # only the new email was saved


def test_access_request_honeypot_and_role_limits(client, fake_db):
    client.post("/access-requests", json={"full_name": "Bot", "email": "bot@test.pk", "website": "spam.com"})
    assert not fake_db.ran("INSERT INTO AccessRequests")
    r = client.post("/access-requests", json={"full_name": "X Y", "email": "x@test.pk", "requested_role": "admin"})
    assert r.status_code == 422                                           # nobody can ask to be admin


def test_admin_approves_access_request(client, fake_db):
    fake_db.on("SELECT * FROM AccessRequests", {"request_id": 5, "full_name": "New", "email": "new@test.pk",
                                                "requested_role": "viewer", "status": "pending"})
    r = client.post("/access-requests/5/decide", headers=headers(1), json={"decision": "approved"})
    assert r.status_code == 200 and r.json()["role"] == "viewer" and r.json()["temporary_password"]
    assert client.post("/access-requests/5/decide", headers=headers(2), json={"decision": "approved"}).status_code == 403


# --- citizen portal --------------------------------------------------------
def challan_row(**extra):
    row = {"challan_id": 9, "challan_no": "RG-20261027-00010", "fine_amount": 2000, "issued_at": datetime.now(),
           "status": "unpaid", "paid_at": None, "payment_ref": None, "violation_id": 10, "violation_type": "NO_HELMET",
           "plate_text": "LEA-1234", "detected_at": datetime.now(), "evidence_file": "ev_x.jpg",
           "camera_name": "Saddar", "location": "Bank Road"}
    row.update(extra)
    return row


def citizen_db(fake_db, **extra):
    fake_db.on("WHERE ch.challan_no = ?", {"challan_id": 9, "plate_text": "LEA-1234"})
    fake_db.on("WHERE ch.challan_id = ?", lambda p: challan_row(**extra))


def test_citizen_lookup_needs_plate_and_challan_no(client, fake_db):
    citizen_db(fake_db)
    ok = client.post("/public/challans/lookup", json={"plate": "lea 1234", "challan_no": "rg-20261027-00010"})
    assert ok.status_code == 200 and ok.json()["fine"] == 2000 and ok.json()["token"]
    wrong_plate = client.post("/public/challans/lookup", json={"plate": "LEB-1234", "challan_no": "RG-20261027-00010"})
    fake_db.on("WHERE ch.challan_no = ?", None)
    wrong_no = client.post("/public/challans/lookup", json={"plate": "LEA-1234", "challan_no": "RG-20261027-99999"})
    assert wrong_plate.status_code == wrong_no.status_code == 404
    assert wrong_plate.json() == wrong_no.json()                          # attacker cannot tell which part was wrong


def test_officer_token_is_not_a_citizen_token(client, fake_db):
    citizen_db(fake_db)
    officer_token = headers(2)["Authorization"].split()[1]
    assert client.post("/public/challans/pay", json={"token": officer_token}).status_code == 401


def test_demo_payment_and_no_double_payment(client, fake_db):
    citizen_db(fake_db)
    token = client.post("/public/challans/lookup", json={"plate": "LEA1234", "challan_no": "RG-20261027-00010"}).json()["token"]
    r = client.post("/public/challans/pay", json={"token": token})
    assert r.status_code == 200 and r.json()["payment_ref"].startswith("DEMO-")
    citizen_db(fake_db, status="paid")
    assert client.post("/public/challans/pay", json={"token": token}).status_code == 400


def test_appeal_flow(client, fake_db):
    citizen_db(fake_db)
    token = client.post("/public/challans/lookup", json={"plate": "LEA1234", "challan_no": "RG-20261027-00010"}).json()["token"]
    short = client.post("/public/challans/appeal", json={"token": token, "reason": "no"})
    assert short.status_code == 422
    r = client.post("/public/challans/appeal", json={"token": token, "reason": "I was wearing a helmet, see the photo."})
    assert r.status_code == 201
    fake_db.on("FROM Appeals a \"", None)
    fake_db.on("JOIN Challans ch ON a.challan_id = ch.challan_id WHERE a.appeal_id = ?",
               {"appeal_id": 1, "status": "pending", "challan_id": 9, "challan_no": "RG-1"})
    decided = client.post("/appeals/1/decide", headers=headers(2), json={"decision": "accepted", "response": "Helmet visible"})
    assert decided.status_code == 200 and decided.json()["challan_status"] == "cancelled"
    assert fake_db.ran("SET status = 'cancelled'")


# --- reports -----------------------------------------------------------------
def test_csv_blocks_formula_injection(client, fake_db):
    fake_db.on("ORDER BY v.violation_id", [{
        "violation_id": 1, "created_at": datetime(2026, 10, 1, 9, 0), "camera": "=HYPERLINK(\"evil\")",
        "violation_type": "NO_HELMET", "confidence": 0.9, "riders": 1, "plate_text": "LEA-1234", "status": "approved",
        "reviewed_by": "Officer", "reviewed_at": None, "challan_no": None, "fine_amount": None, "challan_status": None}])
    r = client.get("/reports/violations.csv", headers=headers(2))
    assert r.status_code == 200 and "'=HYPERLINK" in r.text


def test_pdf_report(client, fake_db):
    r = client.get("/reports/summary.pdf", headers=headers(2))
    assert r.status_code == 200 and r.content[:4] == b"%PDF"


# --- camera streams --------------------------------------------------------
def test_stream_url_rules():
    from app.services.streams import mask_url, validate_url
    assert mask_url("rtsp://admin:secret@10.0.0.5:554/live") == "rtsp://***@10.0.0.5:554/live"
    assert validate_url("http://192.168.1.4:8080/video").startswith("http://")
    for bad in ("file:///C:/Windows/win.ini", "ftp://x/y", "C:\\video.mp4", "demo:../../.env", "javascript:alert(1)"):
        with pytest.raises(ValueError):
            validate_url(bad)


def test_admin_only_and_password_never_returned(client, fake_db):
    fake_db.on("FROM Cameras c ORDER BY", lambda p: [{"camera_id": 1, "name": "A", "location": None, "latitude": None,
                                                       "longitude": None, "is_active": True,
                                                       "stream_url": "rtsp://admin:secret@10.0.0.5/live",
                                                       "stream_enabled": False, "violations": 0}])
    assert client.get("/cameras", headers=headers(1)).json()[0]["stream_url"] == "rtsp://***@10.0.0.5/live"
    assert client.get("/cameras", headers=headers(2)).json()[0]["stream_url"] is None
    assert client.put("/cameras/1/stream", headers=headers(2), json={"stream_enabled": True}).status_code == 403


def test_demo_stream_runs_and_saves_violations(fake_db, monkeypatch, blank_frame):
    from app.services import analyzer, streams
    offender = [det("motorcyclist", (20, 100, 220, 450)), det("no_helmet", (90, 110, 140, 160), 0.85)]
    monkeypatch.setattr(analyzer, "default_detector", FakeDetector(offender))
    monkeypatch.setattr(analyzer, "default_reader", FakeReader())
    monkeypatch.setattr(analyzer, "default_helper", None)
    monkeypatch.setattr(config, "STREAM_FPS", 20)
    path = os.path.join(streams.DEMO_DIR, "unit_test.avi")
    writer = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), 25, (640, 480))
    for _ in range(25):
        writer.write(blank_frame)
    writer.release()
    try:
        stream = streams.stream_manager.start(77, "Test cam", "demo:unit_test.avi", 1)
        time.sleep(2.5)
        info = stream.info()
        assert info["status"] == "live" and info["frames_analysed"] >= 5
        assert streams.stream_manager.snapshot(77)[:2] == b"\xff\xd8"          # a JPEG picture
        streams.stream_manager.stop(77)
        assert stream.violations == 1                                         # same bike all the time = one violation
        assert fake_db.ran("kind, original_name, status, stage")
    finally:
        streams.stream_manager.stop(77)
        os.remove(path)


# --- live events -------------------------------------------------------------
def test_event_bus_filters_by_role_and_masks_plates():
    import asyncio
    from app.services.events import EventBus

    async def scenario():
        bus = EventBus()
        _, officer_q = bus.subscribe("officer")
        _, viewer_q = bus.subscribe("viewer")
        bus.publish({"type": "violation", "plate": "LEA-1234"})
        bus.publish({"type": "access_request"}, roles=("admin",))
        await asyncio.sleep(0.05)
        return officer_q.get_nowait(), viewer_q.get_nowait(), officer_q.qsize(), viewer_q.qsize()

    officer, viewer, left_o, left_v = asyncio.run(scenario())
    assert officer["plate"] == "LEA-1234" and viewer["plate"] == "LEA-**34"
    assert left_o == 0 and left_v == 0                                         # admin-only event not delivered


def test_events_need_login(client):
    assert client.get("/events").status_code == 401
