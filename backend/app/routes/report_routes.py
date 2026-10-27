"""
report_routes.py - Map data and downloadable reports.

  GET /stats/map                 any user: each camera with its GPS position and violation counts
  GET /reports/violations.csv    officer: every violation in the period (opens in Excel)
  GET /reports/summary.pdf       officer: one-page management report for the period
"""
import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app import config
from app.core.auth import ANY_USER, OFFICER
from app.core.security import client_ip
from app.database import execute_query
from app.services.audit import audit

router = APIRouter(tags=["Map & reports"])
PERIOD = "v.created_at >= DATEADD(day, -?, SYSDATETIME())"


def _days(days: int) -> int:
    return max(1, min(int(days), 365))


@router.get("/stats/map")
def map_data(days: int = 30, current_user: dict = Depends(ANY_USER)):
    rows = execute_query(
        f"""SELECT c.camera_id, c.name, c.location, c.latitude, c.longitude, c.is_active, c.stream_enabled,
                   SUM(CASE WHEN v.violation_type = 'NO_HELMET' THEN 1 ELSE 0 END) AS no_helmet,
                   SUM(CASE WHEN v.violation_type = 'TRIPLE_RIDING' THEN 1 ELSE 0 END) AS triple_riding,
                   COUNT(v.violation_id) AS total, MAX(v.created_at) AS last_violation
            FROM Cameras c LEFT JOIN Violations v ON v.camera_id = c.camera_id AND {PERIOD}
            WHERE c.latitude IS NOT NULL AND c.longitude IS NOT NULL
            GROUP BY c.camera_id, c.name, c.location, c.latitude, c.longitude, c.is_active, c.stream_enabled""",
        (_days(days),), fetch_all=True) or []
    for row in rows:
        row["latitude"], row["longitude"] = float(row["latitude"]), float(row["longitude"])
        row["no_helmet"], row["triple_riding"] = row["no_helmet"] or 0, row["triple_riding"] or 0
    return rows


def _violations(days, status=None):
    where, params = [PERIOD], [_days(days)]
    if status in ("pending", "approved", "rejected"):
        where.append("v.status = ?")
        params.append(status)
    return execute_query(
        f"""SELECT v.violation_id, v.created_at, ISNULL(c.name, 'Uploaded media') AS camera, v.violation_type,
                   v.confidence, v.riders, v.plate_text, v.status, r.full_name AS reviewed_by, v.reviewed_at,
                   ch.challan_no, ch.fine_amount, ch.status AS challan_status
            FROM Violations v LEFT JOIN Cameras c ON v.camera_id = c.camera_id
            LEFT JOIN Users r ON v.reviewed_by = r.user_id
            LEFT JOIN Challans ch ON ch.violation_id = v.violation_id
            WHERE {' AND '.join(where)} ORDER BY v.violation_id""", tuple(params), fetch_all=True) or []


def _safe_cell(value):
    """Stop 'CSV injection': Excel runs cells that start with = + - @ as formulas."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


@router.get("/reports/violations.csv")
def violations_csv(request: Request, days: int = 30, status: str = None, current_user: dict = Depends(OFFICER)):
    rows = _violations(days, status)
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["ID", "Detected", "Camera", "Offence", "AI confidence", "People on bike", "Plate", "Status",
                     "Reviewed by", "Reviewed at", "Challan", "Fine (Rs)", "Challan status"])
    for r in rows:
        writer.writerow([_safe_cell(x) for x in (
            r["violation_id"], f"{r['created_at']:%Y-%m-%d %H:%M}", r["camera"],
            config.VIOLATION_LABELS.get(r["violation_type"], r["violation_type"]), f"{r['confidence']:.2f}",
            r["riders"], r["plate_text"], r["status"], r["reviewed_by"],
            f"{r['reviewed_at']:%Y-%m-%d %H:%M}" if r["reviewed_at"] else "", r["challan_no"], r["fine_amount"],
            r["challan_status"])])
    audit(current_user["user_id"], "report_csv", f"{_days(days)} days", None, client_ip(request))
    name = f"roadguard_violations_{datetime.now():%Y%m%d}.csv"
    return Response("﻿" + out.getvalue(), media_type="text/csv; charset=utf-8",      # BOM so Excel reads UTF-8
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/reports/summary.pdf")
def summary_pdf(request: Request, days: int = 30, current_user: dict = Depends(OFFICER)):
    days = _days(days)
    rows = _violations(days)
    styles = getSampleStyleSheet()
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm)
    navy = colors.HexColor("#1f2a44")

    def table(data, widths):
        t = Table(data, colWidths=widths)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), navy), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        return t

    total = len(rows)
    by_status = {s: sum(1 for r in rows if r["status"] == s) for s in ("pending", "approved", "rejected")}
    reviewed = by_status["approved"] + by_status["rejected"]
    challans = [r for r in rows if r["challan_no"]]
    paid = [r for r in challans if r["challan_status"] == "paid"]
    story = [
        Paragraph(f"RoadGuard report - last {days} days", styles["Title"]),
        Paragraph(f"{config.CHALLAN_AUTHORITY} &nbsp;|&nbsp; made {datetime.now():%d %b %Y %H:%M} by "
                  f"{current_user['full_name']}", styles["Normal"]),
        Spacer(1, 8 * mm),
        table([["Violations", "Waiting review", "Approved", "Rejected", "Officer agreement", "E-challans", "Paid"],
               [total, by_status["pending"], by_status["approved"], by_status["rejected"],
                f"{by_status['approved'] / reviewed * 100:.0f}%" if reviewed else "-", len(challans),
                f"Rs {sum(r['fine_amount'] or 0 for r in paid):,}"]], [24 * mm] * 7),
        Spacer(1, 7 * mm), Paragraph("By camera", styles["Heading2"]),
    ]
    cameras = {}
    for r in rows:
        c = cameras.setdefault(r["camera"], {"NO_HELMET": 0, "TRIPLE_RIDING": 0})
        c[r["violation_type"]] += 1
    story.append(table([["Camera", "No helmet", "Triple riding", "Total"]] +
                       [[name, c["NO_HELMET"], c["TRIPLE_RIDING"], c["NO_HELMET"] + c["TRIPLE_RIDING"]]
                        for name, c in sorted(cameras.items(), key=lambda x: -sum(x[1].values()))] or
                       [["-", 0, 0, 0]], [80 * mm, 30 * mm, 30 * mm, 30 * mm]))
    plates = {}
    for r in rows:
        if r["plate_text"] and r["status"] != "rejected":
            plates[r["plate_text"]] = plates.get(r["plate_text"], 0) + 1
    repeat = sorted(((p, n) for p, n in plates.items() if n >= 2), key=lambda x: -x[1])[:10]
    story += [Spacer(1, 7 * mm), Paragraph("Repeat offenders", styles["Heading2"]),
              table([["Number plate", "Violations"]] + ([[p, n] for p, n in repeat] or [["none", "-"]]),
                    [80 * mm, 30 * mm]),
              Spacer(1, 10 * mm),
              Paragraph("Every violation in this report was detected by AI and checked by a human officer before "
                        "a challan was issued. Demo report from a portfolio project.", styles["Italic"])]
    doc.build(story)
    audit(current_user["user_id"], "report_pdf", f"{days} days", None, client_ip(request))
    return Response(buffer.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="roadguard_report_{datetime.now():%Y%m%d}.pdf"'})
