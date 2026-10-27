"""
auth_routes.py - Login and user management.

  POST /auth/login                    -> token (5 wrong passwords lock the account for 15 minutes)
  GET  /auth/me                       -> who am I
  PUT  /auth/profile                  -> change my name
  POST /auth/change-password          -> new password; all OTHER sessions are logged out
  POST /auth/logout-everywhere        -> end every session of this account
  GET  /users                         (admin) list users
  POST /users                         (admin) create an officer / viewer / admin
  PUT  /users/{user_id}               (admin) change role or disable
  POST /users/{user_id}/reset-password (admin) temporary password, must be changed at next login
  POST /access-requests               PUBLIC: "please give me an account" (from the login page)
  GET  /access-requests               (admin) the waiting list
  POST /access-requests/{id}/decide   (admin) approve (creates the account) or reject

There is NO open sign-up: in a traffic system an admin decides who gets an account.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request

from app import config
from app.core.auth import ADMIN, ANY_USER
from app.core.security import (check_password_rules, client_ip, create_token, enforce_rate_limit,
                               hash_password, temporary_password, verify_password)
from app.database import execute_insert_and_get_id, execute_query
from app.schemas import (AccessDecision, AccessRequestIn, LoginRequest, PasswordChange, ProfileUpdate, UserCreate,
                         UserUpdate)
from app.services.events import event_bus
from app.services.audit import audit

router = APIRouter(tags=["Login & users"])
GENERIC_LOGIN_ERROR = "Wrong email or password."      # same message for both: attackers learn nothing


@router.post("/auth/login")
def login(body: LoginRequest, request: Request):
    enforce_rate_limit(request, "login", config.RATE_LIMIT_LOGIN)
    user = execute_query(
        "SELECT user_id, full_name, email, password_hash, role, is_active, failed_logins, locked_until, "
        "must_change_password, token_version FROM Users WHERE email = ?", (body.email.lower(),), fetch_one=True)

    if user and user["locked_until"] and user["locked_until"] > datetime.now():
        raise HTTPException(423, f"Account locked after too many wrong passwords. "
                                 f"Try again in {config.LOGIN_LOCK_MINUTES} minutes.")

    if not user or not verify_password(body.password, user["password_hash"]):
        if user:
            failed = (user["failed_logins"] or 0) + 1
            locked = datetime.now() + timedelta(minutes=config.LOGIN_LOCK_MINUTES) \
                if failed >= config.LOGIN_MAX_ATTEMPTS else None
            execute_query("UPDATE Users SET failed_logins = ?, locked_until = ? WHERE user_id = ?",
                          (0 if locked else failed, locked, user["user_id"]), commit=True)
            audit(user["user_id"], "login_failed", body.email, "account locked" if locked else None, client_ip(request))
        raise HTTPException(401, GENERIC_LOGIN_ERROR)

    if not user["is_active"]:
        raise HTTPException(403, "This account is disabled. Contact an admin.")

    execute_query("UPDATE Users SET failed_logins = 0, locked_until = NULL, last_login = SYSDATETIME() "
                  "WHERE user_id = ?", (user["user_id"],), commit=True)
    audit(user["user_id"], "login", user["email"], None, client_ip(request))
    return _session(user)


def _session(user):
    return {
        "access_token": create_token(user["user_id"], user["email"], user["role"], user.get("token_version") or 0),
        "token_type": "bearer",
        "user": {"user_id": user["user_id"], "full_name": user["full_name"], "email": user["email"],
                 "role": user["role"], "must_change_password": bool(user.get("must_change_password"))},
    }


@router.get("/auth/me")
def me(current_user: dict = Depends(ANY_USER)):
    activity = execute_query(
        "SELECT TOP 10 action, target, created_at FROM AuditLog WHERE user_id = ? ORDER BY audit_id DESC",
        (current_user["user_id"],), fetch_all=True) or []
    last_login = execute_query("SELECT last_login, created_at FROM Users WHERE user_id = ?",
                               (current_user["user_id"],), fetch_one=True) or {}
    return {"user_id": current_user["user_id"], "full_name": current_user["full_name"],
            "email": current_user["email"], "role": current_user["role"],
            "must_change_password": bool(current_user.get("must_change_password")),
            "last_login": last_login.get("last_login"), "created_at": last_login.get("created_at"),
            "recent_activity": activity}


@router.put("/auth/profile")
def update_profile(body: ProfileUpdate, request: Request, current_user: dict = Depends(ANY_USER)):
    execute_query("UPDATE Users SET full_name = ? WHERE user_id = ?",
                  (body.full_name.strip(), current_user["user_id"]), commit=True)
    audit(current_user["user_id"], "profile_changed", None, None, client_ip(request))
    return {"status": "success", "full_name": body.full_name.strip()}


@router.post("/auth/change-password")
def change_password(body: PasswordChange, request: Request, current_user: dict = Depends(ANY_USER)):
    enforce_rate_limit(request, "password", config.RATE_LIMIT_LOGIN)
    row = execute_query("SELECT password_hash FROM Users WHERE user_id = ?", (current_user["user_id"],), fetch_one=True)
    if not row or not verify_password(body.old_password, row["password_hash"]):
        raise HTTPException(400, "Your current password is wrong.")
    if body.new_password == body.old_password:
        raise HTTPException(400, "The new password must be different.")
    check_password_rules(body.new_password)
    # token_version + 1: every OTHER session (other browsers, a stolen token) stops working
    execute_query("UPDATE Users SET password_hash = ?, must_change_password = 0, "
                  "token_version = token_version + 1 WHERE user_id = ?",
                  (hash_password(body.new_password), current_user["user_id"]), commit=True)
    audit(current_user["user_id"], "password_changed", None, None, client_ip(request))
    user = execute_query("SELECT user_id, full_name, email, role, must_change_password, token_version FROM Users "
                         "WHERE user_id = ?", (current_user["user_id"],), fetch_one=True)
    return _session(user)          # a fresh token for THIS browser


@router.post("/auth/logout-everywhere")
def logout_everywhere(request: Request, current_user: dict = Depends(ANY_USER)):
    execute_query("UPDATE Users SET token_version = token_version + 1 WHERE user_id = ?",
                  (current_user["user_id"],), commit=True)
    audit(current_user["user_id"], "logout_everywhere", None, None, client_ip(request))
    return {"status": "success"}


@router.get("/users")
def list_users(current_user: dict = Depends(ADMIN)):
    return execute_query(
        "SELECT user_id, full_name, email, role, is_active, last_login, created_at FROM Users ORDER BY user_id",
        fetch_all=True) or []


@router.post("/users", status_code=201)
def create_user(body: UserCreate, request: Request, current_user: dict = Depends(ADMIN)):
    check_password_rules(body.password)
    if execute_query("SELECT 1 AS x FROM Users WHERE email = ?", (body.email.lower(),), fetch_one=True):
        raise HTTPException(409, "A user with this email already exists.")
    user_id = execute_insert_and_get_id(
        "INSERT INTO Users (full_name, email, password_hash, role) OUTPUT INSERTED.user_id VALUES (?, ?, ?, ?)",
        (body.full_name.strip(), body.email.lower(), hash_password(body.password), body.role))
    audit(current_user["user_id"], "user_created", body.email.lower(), f"role={body.role}", client_ip(request))
    return {"user_id": user_id}


@router.put("/users/{user_id}")
def update_user(user_id: int, body: UserUpdate, request: Request, current_user: dict = Depends(ADMIN)):
    if user_id == current_user["user_id"]:
        raise HTTPException(400, "You cannot change your own role or disable yourself.")
    if not execute_query("SELECT 1 AS x FROM Users WHERE user_id = ?", (user_id,), fetch_one=True):
        raise HTTPException(404, "User not found.")
    if body.role is not None:
        execute_query("UPDATE Users SET role = ? WHERE user_id = ?", (body.role, user_id), commit=True)
    if body.is_active is not None:
        execute_query("UPDATE Users SET is_active = ? WHERE user_id = ?", (1 if body.is_active else 0, user_id),
                      commit=True)
    audit(current_user["user_id"], "user_changed", str(user_id), body.model_dump_json(exclude_none=True),
          client_ip(request))
    return {"status": "success"}


@router.post("/users/{user_id}/reset-password")
def reset_password(user_id: int, request: Request, current_user: dict = Depends(ADMIN)):
    """Admin gives a temporary password (shown ONCE). The user must change it at the next login."""
    if user_id == current_user["user_id"]:
        raise HTTPException(400, "Use your Profile page to change your own password.")
    target = execute_query("SELECT email FROM Users WHERE user_id = ?", (user_id,), fetch_one=True)
    if not target:
        raise HTTPException(404, "User not found.")
    password = temporary_password()
    execute_query("UPDATE Users SET password_hash = ?, must_change_password = 1, token_version = token_version + 1, "
                  "failed_logins = 0, locked_until = NULL WHERE user_id = ?",
                  (hash_password(password), user_id), commit=True)
    audit(current_user["user_id"], "password_reset", target["email"], None, client_ip(request))
    return {"temporary_password": password, "email": target["email"]}


# ---------------------------------------------------------------------------
# Access requests ("I am an officer, please give me an account")
# ---------------------------------------------------------------------------
@router.post("/access-requests", status_code=201)
def request_access(body: AccessRequestIn, request: Request):
    enforce_rate_limit(request, "access_request", (5, 3600))         # 5 per hour per IP
    if body.website:                                                   # hidden field: only bots fill it
        return {"status": "received"}
    email = body.email.lower()
    exists = execute_query("SELECT 1 AS x FROM Users WHERE email = ?", (email,), fetch_one=True) or \
        execute_query("SELECT 1 AS x FROM AccessRequests WHERE email = ? AND status = 'pending'", (email,), fetch_one=True)
    if not exists:                       # same answer either way, so nobody can test which emails have accounts
        request_id = execute_insert_and_get_id(
            "INSERT INTO AccessRequests (full_name, email, organisation, reason, requested_role, ip_address) "
            "OUTPUT INSERTED.request_id VALUES (?, ?, ?, ?, ?, ?)",
            (body.full_name.strip(), email, body.organisation, body.reason, body.requested_role, client_ip(request)))
        event_bus.publish({"type": "access_request", "request_id": request_id, "name": body.full_name.strip()},
                          roles=("admin",))
    return {"status": "received"}


@router.get("/access-requests")
def list_access_requests(status: str = "pending", current_user: dict = Depends(ADMIN)):
    return execute_query(
        """SELECT r.request_id, r.full_name, r.email, r.organisation, r.reason, r.requested_role, r.status,
                  r.created_at, r.decided_at, u.full_name AS decided_by_name
           FROM AccessRequests r LEFT JOIN Users u ON r.decided_by = u.user_id
           WHERE r.status = ? ORDER BY r.request_id DESC""", (status,), fetch_all=True) or []


@router.post("/access-requests/{request_id}/decide")
def decide_access_request(request_id: int, body: AccessDecision, request: Request, current_user: dict = Depends(ADMIN)):
    row = execute_query("SELECT * FROM AccessRequests WHERE request_id = ?", (request_id,), fetch_one=True)
    if not row or row["status"] != "pending":
        raise HTTPException(404, "No waiting request with this number.")
    result = {"status": body.decision}
    if body.decision == "approved":
        if execute_query("SELECT 1 AS x FROM Users WHERE email = ?", (row["email"],), fetch_one=True):
            raise HTTPException(409, "A user with this email already exists.")
        password = temporary_password()
        role = body.role or row["requested_role"]
        user_id = execute_insert_and_get_id(
            "INSERT INTO Users (full_name, email, password_hash, role, must_change_password) "
            "OUTPUT INSERTED.user_id VALUES (?, ?, ?, ?, 1)",
            (row["full_name"], row["email"], hash_password(password), role))
        result.update({"user_id": user_id, "email": row["email"], "temporary_password": password, "role": role})
    execute_query("UPDATE AccessRequests SET status = ?, decided_by = ?, decided_at = SYSDATETIME() "
                  "WHERE request_id = ?", (body.decision, current_user["user_id"], request_id), commit=True)
    audit(current_user["user_id"], f"access_{body.decision}", row["email"], None, client_ip(request))
    return result


@router.get("/audit")
def audit_log(limit: int = 200, current_user: dict = Depends(ADMIN)):
    limit = max(1, min(limit, 1000))
    return execute_query(
        f"""SELECT TOP ({limit}) a.audit_id, a.action, a.target, a.details, a.ip_address, a.created_at,
                   u.full_name AS user_name
            FROM AuditLog a LEFT JOIN Users u ON a.user_id = u.user_id ORDER BY a.audit_id DESC""",
        fetch_all=True) or []
