"""
audit.py - Writes an audit trail: who did what, when, from which IP.

Logged actions: login (ok / failed), user created / changed, violation approved /
rejected / plate corrected, challan issued, camera changed.
An audit log is required in real enforcement systems, and it is how you
investigate misuse ("who approved this challan?").
"""
import logging

from app.database import execute_query

log = logging.getLogger("audit")


def audit(user_id, action: str, target: str = None, details: str = None, ip: str = None):
    try:
        execute_query(
            "INSERT INTO AuditLog (user_id, action, target, details, ip_address) VALUES (?, ?, ?, ?, ?)",
            (user_id, action[:50], (target or "")[:100], (details or "")[:400], (ip or "")[:50]), commit=True)
    except Exception:
        log.exception("Audit write failed")         # never block the real action because of the log
