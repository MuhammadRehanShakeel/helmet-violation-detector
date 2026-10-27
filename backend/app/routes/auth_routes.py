"""
auth_routes.py - Login and user management.

  POST /auth/login                 -> token (5 wrong passwords lock the account for 15 minutes)
  GET  /auth/me                    -> who am I
  POST /auth/change-password
  GET  /users                      (admin) list users
  POST /users                      (admin) create an officer / viewer / admin
  PUT  /users/{user_id}            (admin) change role or disable

There is NO public sign-up: in a traffic system only an admin creates accounts.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request

from app import config
from app.core.auth import ADMIN, ANY_USER
from app.core.security import (check_password_rules, client_ip, create_token, enforce_rate_limit,
                               hash_password, verify_password)
from app.database import execute_insert_and_get_id, execute_query
from app.schemas import LoginRequest, PasswordChange, UserCreate, UserUpdate
from app.services.audit import audit

router = APIRouter(tags=["Login & users"])
GENERIC_LOGIN_ERROR = "Wrong email or password."      # same message for both: attackers learn nothing


@router.post("/auth/login")
def login(body: LoginRequest, request: Request):
    enforce_rate_limit(request, "login", config.RATE_LIMIT_LOGIN)
    user = execute_query(
        "SELECT user_id, full_name, email, password_hash, role, is_active, failed_logins, locked_until "
        "FROM Users WHERE email = ?", (body.email.lower(),), fetch_one=True)

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
    return {
        "access_token": create_token(user["user_id"], user["email"], user["role"]),
        "token_type": "bearer",
        "user": {"user_id": user["user_id"], "full_name": user["full_name"],
                 "email": user["email"], "role": user["role"]},
    }


@router.get("/auth/me")
def me(current_user: dict = Depends(ANY_USER)):
    return current_user


@router.post("/auth/change-password")
def change_password(body: PasswordChange, request: Request, current_user: dict = Depends(ANY_USER)):
    row = execute_query("SELECT password_hash FROM Users WHERE user_id = ?", (current_user["user_id"],), fetch_one=True)
    if not row or not verify_password(body.old_password, row["password_hash"]):
        raise HTTPException(400, "Your current password is wrong.")
    check_password_rules(body.new_password)
    execute_query("UPDATE Users SET password_hash = ? WHERE user_id = ?",
                  (hash_password(body.new_password), current_user["user_id"]), commit=True)
    audit(current_user["user_id"], "password_changed", None, None, client_ip(request))
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


@router.get("/audit")
def audit_log(limit: int = 200, current_user: dict = Depends(ADMIN)):
    limit = max(1, min(limit, 1000))
    return execute_query(
        f"""SELECT TOP ({limit}) a.audit_id, a.action, a.target, a.details, a.ip_address, a.created_at,
                   u.full_name AS user_name
            FROM AuditLog a LEFT JOIN Users u ON a.user_id = u.user_id ORDER BY a.audit_id DESC""",
        fetch_all=True) or []
