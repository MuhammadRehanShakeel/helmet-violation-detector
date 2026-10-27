"""
stats_routes.py - Numbers for the dashboard.

  GET /stats/summary?days=30   totals, per type, per status, per day, per hour, per camera,
                               top repeat offenders, average AI confidence
"""
from fastapi import APIRouter, Depends

from app import config
from app.core.auth import ANY_USER, mask_plate
from app.database import execute_query

router = APIRouter(prefix="/stats", tags=["Dashboard"])


@router.get("/summary")
def summary(days: int = 30, current_user: dict = Depends(ANY_USER)):
    days = max(1, min(days, 365))
    since = "v.created_at >= DATEADD(day, -?, SYSDATETIME())"
    p = (days,)

    totals = execute_query(
        f"""SELECT COUNT(*) AS violations,
                   SUM(CASE WHEN v.status = 'pending' THEN 1 ELSE 0 END) AS pending,
                   SUM(CASE WHEN v.status = 'approved' THEN 1 ELSE 0 END) AS approved,
                   SUM(CASE WHEN v.status = 'rejected' THEN 1 ELSE 0 END) AS rejected,
                   SUM(CASE WHEN v.plate_valid = 1 THEN 1 ELSE 0 END) AS plates_read,
                   AVG(v.confidence) AS avg_confidence
            FROM Violations v WHERE {since}""", p, fetch_one=True) or {}
    jobs = execute_query(
        """SELECT COUNT(*) AS jobs, ISNULL(SUM(motorcyclists), 0) AS motorcyclists FROM Jobs
           WHERE created_at >= DATEADD(day, -?, SYSDATETIME()) AND status = 'done'""", p, fetch_one=True) or {}
    challans = execute_query(
        """SELECT COUNT(*) AS n, ISNULL(SUM(fine_amount), 0) AS amount FROM Challans
           WHERE issued_at >= DATEADD(day, -?, SYSDATETIME())""", p, fetch_one=True) or {}

    by_type = execute_query(
        f"SELECT v.violation_type AS type, COUNT(*) AS n FROM Violations v WHERE {since} GROUP BY v.violation_type",
        p, fetch_all=True) or []
    by_day = execute_query(
        f"""SELECT CAST(v.created_at AS DATE) AS day, v.violation_type AS type, COUNT(*) AS n
            FROM Violations v WHERE {since} GROUP BY CAST(v.created_at AS DATE), v.violation_type ORDER BY day""",
        p, fetch_all=True) or []
    by_hour = execute_query(
        f"SELECT DATEPART(hour, v.created_at) AS hour, COUNT(*) AS n FROM Violations v WHERE {since} "
        "GROUP BY DATEPART(hour, v.created_at) ORDER BY hour", p, fetch_all=True) or []
    by_camera = execute_query(
        f"""SELECT ISNULL(c.name, 'Uploaded media') AS camera, COUNT(*) AS n FROM Violations v
            LEFT JOIN Cameras c ON v.camera_id = c.camera_id WHERE {since}
            GROUP BY ISNULL(c.name, 'Uploaded media') ORDER BY n DESC""", p, fetch_all=True) or []
    repeat = execute_query(
        f"""SELECT TOP 10 v.plate_text AS plate, COUNT(*) AS n FROM Violations v
            WHERE {since} AND v.plate_text IS NOT NULL AND v.status <> 'rejected'
            GROUP BY v.plate_text HAVING COUNT(*) >= 2 ORDER BY n DESC""", p, fetch_all=True) or []

    reviewed = (totals.get("approved") or 0) + (totals.get("rejected") or 0)
    return {
        "days": days,
        "violations": totals.get("violations") or 0,
        "pending": totals.get("pending") or 0,
        "approved": totals.get("approved") or 0,
        "rejected": totals.get("rejected") or 0,
        # how often officers agreed with the AI = real-world precision
        "officer_agreement": round((totals.get("approved") or 0) / reviewed * 100, 1) if reviewed else None,
        "plates_read_percent": round((totals.get("plates_read") or 0) / totals["violations"] * 100, 1)
        if totals.get("violations") else None,
        "avg_confidence": round(totals.get("avg_confidence") or 0, 3),
        "jobs": jobs.get("jobs") or 0,
        "motorcyclists": jobs.get("motorcyclists") or 0,
        "challans": challans.get("n") or 0,
        "fines_amount": challans.get("amount") or 0,
        "by_type": [{**r, "label": config.VIOLATION_LABELS.get(r["type"], r["type"])} for r in by_type],
        "by_day": [{"day": str(r["day"]), "type": r["type"], "n": r["n"]} for r in by_day],
        "by_hour": by_hour,
        "by_camera": by_camera,
        "repeat_offenders": [{"plate": mask_plate(r["plate"], current_user["role"]), "n": r["n"]} for r in repeat],
    }
