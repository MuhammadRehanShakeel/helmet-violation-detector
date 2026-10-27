"""
violation_routes.py - The review desk: every AI result is checked by a human.

  GET  /violations                       list + filters (status, type, camera, plate, job, low confidence)
  GET  /violations/{id}                  one violation (+ its challan if issued)
  GET  /violations/{id}/image/{kind}     evidence | crop | plate   (logged-in users only)
  PUT  /violations/{id}/review           (officer) approve / reject, optionally correct the plate
  POST /violations/{id}/challan          (officer) issue the e-challan PDF (approved violations only)
  GET  /challans/{challan_id}/pdf        (officer) download the PDF
  GET  /challans/verify/{code}           PUBLIC: is this challan real? (used by the QR code)
  GET  /plates/{plate}                   (officer) history of one number plate (repeat offenders)

Viewers can browse, but number plates are partly hidden and plate photos are blocked.
"""
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from app import config
from app.core.auth import ANY_USER, OFFICER, mask_plate
from app.core.security import client_ip, enforce_rate_limit
from app.database import execute_insert_and_get_id, execute_query
from app.schemas import ReviewRequest
from app.services import challan as challan_service
from app.services.audit import audit
from app.services.plates import compact, normalise_plate

router = APIRouter(tags=["Violations & e-challans"])

COLUMNS = """v.violation_id, v.job_id, v.camera_id, c.name AS camera_name, c.location, v.violation_type,
             v.confidence, v.low_confidence, v.riders, v.no_helmet_count, v.plate_text, v.plate_raw,
             v.plate_valid, v.plate_confidence, v.frame_time, v.status, v.review_note, v.reviewed_at,
             r.full_name AS reviewed_by_name, v.created_at, ch.challan_id, ch.challan_no,
             ch.status AS challan_status"""
FROM = """FROM Violations v LEFT JOIN Cameras c ON v.camera_id = c.camera_id
          LEFT JOIN Users r ON v.reviewed_by = r.user_id
          LEFT JOIN Challans ch ON ch.violation_id = v.violation_id"""
SEARCH_PLATE = "REPLACE(REPLACE(v.plate_text, '-', ''), ' ', '')"


def _shape(row, role):
    row["plate_text"] = mask_plate(row["plate_text"], role)
    if role == "viewer":
        row["plate_raw"] = None
    row["fine"] = config.FINES.get(row["violation_type"], 0)
    row["violation_label"] = config.VIOLATION_LABELS.get(row["violation_type"], row["violation_type"])
    return row


def _get(violation_id: int):
    row = execute_query(f"SELECT {COLUMNS}, v.evidence_file, v.crop_file, v.plate_file {FROM} WHERE v.violation_id = ?",
                        (violation_id,), fetch_one=True)
    if not row:
        raise HTTPException(404, "Violation not found.")
    return row


@router.get("/violations")
def list_violations(status: str = None, violation_type: str = None, camera_id: int = None, plate: str = None,
                    job_id: int = None, low_confidence: bool = None, page: int = 1, page_size: int = 24,
                    current_user: dict = Depends(ANY_USER)):
    where, params = ["1 = 1"], []
    if status in ("pending", "approved", "rejected"):
        where.append("v.status = ?")
        params.append(status)
    if violation_type in config.FINES:
        where.append("v.violation_type = ?")
        params.append(violation_type)
    if camera_id:
        where.append("v.camera_id = ?")
        params.append(camera_id)
    if job_id:
        where.append("v.job_id = ?")
        params.append(job_id)
    if low_confidence is not None:
        where.append("v.low_confidence = ?")
        params.append(1 if low_confidence else 0)
    if plate and current_user["role"] != "viewer":
        where.append(f"{SEARCH_PLATE} LIKE ?")
        params.append(f"%{compact(plate)}%")               # still a parameter: no SQL injection

    page, page_size = max(1, page), max(1, min(page_size, 100))
    condition = " AND ".join(where)
    total = execute_query(f"SELECT COUNT(*) AS n {FROM} WHERE {condition}", tuple(params), fetch_one=True)["n"]
    rows = execute_query(
        f"""SELECT {COLUMNS} {FROM} WHERE {condition} ORDER BY v.violation_id DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY""", tuple(params) + ((page - 1) * page_size, page_size),
        fetch_all=True) or []
    return {"total": total, "page": page, "page_size": page_size,
            "items": [_shape(r, current_user["role"]) for r in rows]}


@router.get("/violations/{violation_id}")
def get_violation(violation_id: int, current_user: dict = Depends(ANY_USER)):
    row = _get(violation_id)
    for key in ("evidence_file", "crop_file", "plate_file"):
        row[key.replace("_file", "_available")] = bool(row.pop(key))
    if current_user["role"] != "viewer" and row["plate_text"]:
        row["previous_violations"] = execute_query(
            f"SELECT COUNT(*) AS n FROM Violations v WHERE {SEARCH_PLATE} = ? AND v.violation_id <> ? "
            "AND v.status <> 'rejected'", (compact(row["plate_text"]), violation_id), fetch_one=True)["n"]
    return _shape(row, current_user["role"])


@router.get("/violations/{violation_id}/image/{kind}")
def violation_image(violation_id: int, kind: str, current_user: dict = Depends(ANY_USER)):
    if kind not in ("evidence", "crop", "plate"):
        raise HTTPException(404, "Unknown image.")
    if kind == "plate" and current_user["role"] == "viewer":
        raise HTTPException(403, "Viewers cannot see number plate photos.")
    row = execute_query(f"SELECT {kind}_file AS f FROM Violations WHERE violation_id = ?", (violation_id,),
                        fetch_one=True)
    if not row or not row["f"]:
        raise HTTPException(404, "Image not found.")
    path = os.path.realpath(os.path.join(config.EVIDENCE_DIR, os.path.basename(row["f"])))
    if not path.startswith(os.path.realpath(config.EVIDENCE_DIR)) or not os.path.isfile(path):
        raise HTTPException(404, "Image not found.")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


@router.put("/violations/{violation_id}/review")
def review(violation_id: int, body: ReviewRequest, request: Request, current_user: dict = Depends(OFFICER)):
    row = _get(violation_id)
    if row["challan_id"]:
        raise HTTPException(409, "An e-challan was already issued for this violation; it cannot be changed.")

    plate_text, plate_valid = row["plate_text"], row["plate_valid"]
    if body.plate_text is not None and body.plate_text.strip():
        cleaned = normalise_plate(body.plate_text)
        if not cleaned["valid"]:
            raise HTTPException(400, "That does not look like a Pakistani number plate (e.g. LEA-1234).")
        plate_text, plate_valid = cleaned["plate"], 1

    if body.decision == "approved" and not plate_text:
        raise HTTPException(400, "Type the number plate before approving (the AI could not read it).")

    execute_query(
        """UPDATE Violations SET status = ?, review_note = ?, plate_text = ?, plate_valid = ?, reviewed_by = ?,
               reviewed_at = SYSDATETIME() WHERE violation_id = ?""",
        (body.decision, body.note, plate_text, plate_valid, current_user["user_id"], violation_id), commit=True)
    details = f"plate {row['plate_text']} -> {plate_text}" if plate_text != row["plate_text"] else body.note
    audit(current_user["user_id"], f"violation_{body.decision}", str(violation_id), details, client_ip(request))
    return {"status": body.decision, "plate_text": plate_text}


@router.post("/violations/{violation_id}/challan", status_code=201)
def issue_challan(violation_id: int, request: Request, current_user: dict = Depends(OFFICER)):
    row = _get(violation_id)
    if row["status"] != "approved":
        raise HTTPException(400, "Only approved violations can get an e-challan.")
    if row["challan_id"]:
        return {"challan_id": row["challan_id"], "challan_no": row["challan_no"], "already_issued": True}

    challan_no, verify_code = challan_service.new_codes(violation_id)
    fine = config.FINES[row["violation_type"]]
    challan_id = execute_insert_and_get_id(
        "INSERT INTO Challans (violation_id, challan_no, verify_code, fine_amount, issued_by) "
        "OUTPUT INSERTED.challan_id VALUES (?, ?, ?, ?, ?)",
        (violation_id, challan_no, verify_code, fine, current_user["user_id"]))
    pdf_name = f"{challan_no}.pdf"
    issued = execute_query("SELECT issued_at FROM Challans WHERE challan_id = ?", (challan_id,), fetch_one=True)
    challan_service.make_pdf(os.path.join(config.CHALLAN_DIR, pdf_name), {
        "challan_no": challan_no, "verify_code": verify_code,
        "issued_at": f"{issued['issued_at']:%d %b %Y %H:%M}", "plate": row["plate_text"],
        "violation_label": config.VIOLATION_LABELS[row["violation_type"]], "fine": fine,
        "camera": row["camera_name"] or "Uploaded media", "location": row["location"] or "-",
        "detected_at": f"{row['created_at']:%d %b %Y %H:%M}", "officer": current_user["full_name"],
        "confidence": row["confidence"],
        "evidence_path": os.path.join(config.EVIDENCE_DIR, row["evidence_file"] or ""),
        "plate_path": os.path.join(config.EVIDENCE_DIR, row["plate_file"]) if row["plate_file"] else None,
    })
    execute_query("UPDATE Challans SET pdf_file = ? WHERE challan_id = ?", (pdf_name, challan_id), commit=True)
    audit(current_user["user_id"], "challan_issued", challan_no, f"violation {violation_id}, Rs {fine}",
          client_ip(request))
    return {"challan_id": challan_id, "challan_no": challan_no, "already_issued": False}


@router.get("/challans/{challan_id}/pdf")
def challan_pdf(challan_id: int, current_user: dict = Depends(OFFICER)):
    row = execute_query("SELECT challan_no, pdf_file FROM Challans WHERE challan_id = ?", (challan_id,), fetch_one=True)
    if not row or not row["pdf_file"]:
        raise HTTPException(404, "Challan not found.")
    path = os.path.join(config.CHALLAN_DIR, os.path.basename(row["pdf_file"]))
    if not os.path.isfile(path):
        raise HTTPException(404, "Challan file missing.")
    return FileResponse(path, media_type="application/pdf", filename=f"{row['challan_no']}.pdf")


@router.get("/challans/verify/{code}")
def verify_challan(code: str, request: Request):
    """Public on purpose (scanned from the paper ticket). Shows only what the ticket already shows."""
    enforce_rate_limit(request, "verify", (30, 60))
    if not 10 <= len(code) <= 40:
        raise HTTPException(404, "No challan found for this code.")
    row = execute_query(
        """SELECT ch.challan_no, ch.fine_amount, ch.issued_at, ch.status, v.violation_type, v.plate_text
           FROM Challans ch JOIN Violations v ON ch.violation_id = v.violation_id WHERE ch.verify_code = ?""",
        (code,), fetch_one=True)
    if not row:
        raise HTTPException(404, "No challan found for this code.")
    return {"valid": True, "challan_no": row["challan_no"], "fine": row["fine_amount"],
            "issued_at": row["issued_at"], "offence": config.VIOLATION_LABELS[row["violation_type"]],
            "plate": mask_plate(row["plate_text"], "viewer"), "status": row.get("status", "unpaid")}


@router.get("/plates/{plate}")
def plate_history(plate: str, current_user: dict = Depends(OFFICER)):
    key = compact(plate)
    if len(key) < 3:
        raise HTTPException(400, "Type at least 3 characters of the plate.")
    rows = execute_query(
        f"SELECT {COLUMNS} {FROM} WHERE {SEARCH_PLATE} = ? ORDER BY v.violation_id DESC", (key,), fetch_all=True) or []
    items = [_shape(r, current_user["role"]) for r in rows]
    counted = [r for r in items if r["status"] != "rejected"]
    return {"plate": normalise_plate(plate)["plate"] or plate.upper(), "total": len(counted),
            "unpaid_fines": sum(r["fine"] for r in counted if r["status"] == "approved"),
            "repeat_offender": len(counted) >= 2, "items": items}
