"""
citizen_routes.py - The PUBLIC citizen portal + the officers' appeal desk.

Citizen (no account needed):
  POST /public/challans/lookup     plate + challan number -> the challan, evidence link, appeal status
  GET  /public/challans/evidence   evidence photo (needs the token from lookup)
  POST /public/challans/pay        DEMO payment: marks the challan paid (no card details are asked for)
  POST /public/challans/appeal     "this is wrong": reason + optional contact -> officer appeal queue

Officers:
  GET  /appeals?status=pending
  POST /appeals/{appeal_id}/decide   accepted -> challan cancelled; rejected -> challan stays

Why plate AND challan number? Either one alone could be guessed or found on the street.
Both together, plus a rate limit, stop people browsing other people's fines.
After a successful lookup the citizen gets a 30-minute token for that ONE challan.
"""
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from app import config
from app.core.auth import OFFICER
from app.core.security import client_ip, enforce_rate_limit
from app.database import execute_insert_and_get_id, execute_query
from app.schemas import AppealDecision, AppealIn, CitizenAction, CitizenLookup
from app.services.audit import audit
from app.services.events import event_bus
from app.services.plates import compact

router = APIRouter(tags=["Citizen portal & appeals"])
NOT_FOUND = "No challan found with this number plate and challan number."
TOKEN_MINUTES = 30


def _citizen_token(challan_id: int) -> str:
    payload = {"scope": "citizen", "challan_id": challan_id,
               "exp": datetime.now(timezone.utc) + timedelta(minutes=TOKEN_MINUTES)}
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def _challan_from_token(token: str) -> int:
    try:
        payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    except jwt.InvalidTokenError:
        raise HTTPException(401, "This page has expired. Please look up your challan again.")
    if payload.get("scope") != "citizen":                 # an officer's login token is NOT accepted here
        raise HTTPException(401, "This page has expired. Please look up your challan again.")
    return int(payload["challan_id"])


def _details(challan_id: int):
    row = execute_query(
        """SELECT ch.challan_id, ch.challan_no, ch.fine_amount, ch.issued_at, ch.status, ch.paid_at, ch.payment_ref,
                  v.violation_id, v.violation_type, v.plate_text, v.created_at AS detected_at, v.evidence_file,
                  c.name AS camera_name, c.location
           FROM Challans ch JOIN Violations v ON ch.violation_id = v.violation_id
           LEFT JOIN Cameras c ON v.camera_id = c.camera_id WHERE ch.challan_id = ?""", (challan_id,), fetch_one=True)
    if not row:
        raise HTTPException(404, NOT_FOUND)
    appeal = execute_query("SELECT TOP 1 appeal_id, status, response, created_at, decided_at FROM Appeals "
                           "WHERE challan_id = ? ORDER BY appeal_id DESC", (challan_id,), fetch_one=True)
    return row, appeal


@router.post("/public/challans/lookup")
def lookup(body: CitizenLookup, request: Request):
    enforce_rate_limit(request, "citizen_lookup", (20, 600))         # 20 tries per 10 minutes per IP
    row = execute_query(
        """SELECT ch.challan_id, v.plate_text FROM Challans ch JOIN Violations v ON ch.violation_id = v.violation_id
           WHERE ch.challan_no = ?""", (body.challan_no.strip().upper(),), fetch_one=True)
    if not row or compact(row["plate_text"]) != compact(body.plate):
        raise HTTPException(404, NOT_FOUND)                          # same answer: wrong number OR wrong plate
    details, appeal = _details(row["challan_id"])
    return {
        "token": _citizen_token(row["challan_id"]),
        "challan_no": details["challan_no"], "plate": details["plate_text"],
        "offence": config.VIOLATION_LABELS[details["violation_type"]], "fine": details["fine_amount"],
        "status": details["status"], "issued_at": details["issued_at"], "detected_at": details["detected_at"],
        "camera": details["camera_name"] or "Uploaded media", "location": details["location"],
        "paid_at": details["paid_at"], "payment_ref": details["payment_ref"],
        "has_evidence": bool(details["evidence_file"]),
        "appeal": appeal,
    }


@router.get("/public/challans/evidence")
def evidence(token: str, request: Request):
    """The token is in the URL here because an <img> tag cannot send headers; it only opens ONE photo for 30 min."""
    enforce_rate_limit(request, "citizen_evidence", (60, 600))
    details, _ = _details(_challan_from_token(token))
    if not details["evidence_file"]:
        raise HTTPException(404, "No photo for this challan.")
    path = os.path.realpath(os.path.join(config.EVIDENCE_DIR, os.path.basename(details["evidence_file"])))
    if not path.startswith(os.path.realpath(config.EVIDENCE_DIR)) or not os.path.isfile(path):
        raise HTTPException(404, "No photo for this challan.")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})


@router.post("/public/challans/pay")
def pay(body: CitizenAction, request: Request):
    """DEMO ONLY: a real system would redirect to 1Link / JazzCash / Easypaisa. No card details are collected."""
    enforce_rate_limit(request, "citizen_pay", (10, 600))
    challan_id = _challan_from_token(body.token)
    details, appeal = _details(challan_id)
    if details["status"] != "unpaid":
        raise HTTPException(400, f"This challan is already {details['status']}.")
    if appeal and appeal["status"] == "pending":
        raise HTTPException(400, "Your appeal is still being reviewed. Wait for the decision before paying.")
    reference = "DEMO-" + secrets.token_hex(4).upper()
    execute_query("UPDATE Challans SET status = 'paid', paid_at = SYSDATETIME(), payment_ref = ? "
                  "WHERE challan_id = ? AND status = 'unpaid'", (reference, challan_id), commit=True)
    audit(None, "challan_paid_demo", details["challan_no"], reference, client_ip(request))
    event_bus.publish({"type": "payment", "challan_no": details["challan_no"], "amount": details["fine_amount"]},
                      roles=("admin", "officer"))
    return {"status": "paid", "payment_ref": reference}


@router.post("/public/challans/appeal", status_code=201)
def appeal(body: AppealIn, request: Request):
    enforce_rate_limit(request, "citizen_appeal", (5, 3600))
    challan_id = _challan_from_token(body.token)
    details, last = _details(challan_id)
    if details["status"] != "unpaid":
        raise HTTPException(400, "Only unpaid challans can be appealed.")
    if last and last["status"] in ("pending", "rejected"):
        raise HTTPException(400, "An appeal for this challan was already submitted.")
    appeal_id = execute_insert_and_get_id(
        "INSERT INTO Appeals (challan_id, reason, contact) OUTPUT INSERTED.appeal_id VALUES (?, ?, ?)",
        (challan_id, body.reason.strip(), (body.contact or "").strip() or None))
    audit(None, "appeal_submitted", details["challan_no"], None, client_ip(request))
    event_bus.publish({"type": "appeal", "appeal_id": appeal_id, "challan_no": details["challan_no"]},
                      roles=("admin", "officer"))
    return {"appeal_id": appeal_id, "status": "pending"}


# ---------------------------------------------------------------------------
# Officers: the appeal desk
# ---------------------------------------------------------------------------
@router.get("/appeals")
def list_appeals(status: str = "pending", current_user: dict = Depends(OFFICER)):
    if status not in ("pending", "accepted", "rejected"):
        status = "pending"
    rows = execute_query(
        """SELECT a.appeal_id, a.reason, a.contact, a.status, a.response, a.created_at, a.decided_at,
                  u.full_name AS decided_by_name, ch.challan_id, ch.challan_no, ch.fine_amount, ch.status AS challan_status,
                  v.violation_id, v.violation_type, v.plate_text, v.confidence
           FROM Appeals a JOIN Challans ch ON a.challan_id = ch.challan_id
           JOIN Violations v ON ch.violation_id = v.violation_id
           LEFT JOIN Users u ON a.decided_by = u.user_id
           WHERE a.status = ? ORDER BY a.appeal_id DESC""", (status,), fetch_all=True) or []
    for row in rows:
        row["offence"] = config.VIOLATION_LABELS.get(row["violation_type"], row["violation_type"])
    return rows


@router.post("/appeals/{appeal_id}/decide")
def decide_appeal(appeal_id: int, body: AppealDecision, request: Request, current_user: dict = Depends(OFFICER)):
    row = execute_query("SELECT a.appeal_id, a.status, a.challan_id, ch.challan_no FROM Appeals a "
                        "JOIN Challans ch ON a.challan_id = ch.challan_id WHERE a.appeal_id = ?",
                        (appeal_id,), fetch_one=True)
    if not row or row["status"] != "pending":
        raise HTTPException(404, "No waiting appeal with this number.")
    execute_query("UPDATE Appeals SET status = ?, response = ?, decided_by = ?, decided_at = SYSDATETIME() "
                  "WHERE appeal_id = ?", (body.decision, body.response, current_user["user_id"], appeal_id), commit=True)
    if body.decision == "accepted":
        execute_query("UPDATE Challans SET status = 'cancelled' WHERE challan_id = ?", (row["challan_id"],), commit=True)
    audit(current_user["user_id"], f"appeal_{body.decision}", row["challan_no"], body.response[:200], client_ip(request))
    return {"status": body.decision, "challan_status": "cancelled" if body.decision == "accepted" else "unpaid"}

