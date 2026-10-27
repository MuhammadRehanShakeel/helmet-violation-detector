"""
auth.py - "Who is calling, and are they allowed?"

Every protected route adds one of these as a dependency:
    current_user = Depends(get_current_user)          any logged-in user
    current_user = Depends(require_roles("admin"))    only admins
    current_user = Depends(OFFICER)                   admins and officers

The user is re-read from the database on every request, so a disabled
account or a changed role takes effect immediately (not when the token expires).
"""
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_token
from app.database import execute_query

bearer = HTTPBearer(auto_error=False)


# While a user must change a temporary password, only these addresses work
PASSWORD_CHANGE_PATHS = ("/auth/me", "/auth/change-password", "/events")


def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    if credentials is None or not credentials.credentials:
        raise HTTPException(401, "Please log in.")
    payload = decode_token(credentials.credentials)
    user = execute_query(
        "SELECT user_id, full_name, email, role, is_active, must_change_password, token_version "
        "FROM Users WHERE user_id = ?",
        (payload.get("user_id"),), fetch_one=True,
    )
    if not user or not user["is_active"]:
        raise HTTPException(401, "This account is disabled. Contact an admin.")
    if (user.get("token_version") or 0) != payload.get("tv", 0):
        # the password was changed (or "log out everywhere" was used) after this token was made
        raise HTTPException(401, "Your session has ended. Please log in again.")
    if user.get("must_change_password") and not request.url.path.endswith(PASSWORD_CHANGE_PATHS):
        raise HTTPException(403, "Please change your temporary password first.")
    return user


def require_roles(*roles):
    """Build a dependency that only lets the given roles through."""
    def checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in roles:
            raise HTTPException(403, "You do not have permission for this action.")
        return current_user
    return checker


ADMIN = require_roles("admin")
OFFICER = require_roles("admin", "officer")          # people who can analyse and review
ANY_USER = get_current_user


def mask_plate(plate, role: str):
    """Viewers only see part of a number plate (privacy): LEA-1234 -> LEA-**34."""
    if not plate or role in ("admin", "officer"):
        return plate
    letters, _, digits = plate.partition("-")
    if not digits:
        return plate[:2] + "*" * max(0, len(plate) - 2)
    return f"{letters}-{'*' * max(0, len(digits) - 2)}{digits[-2:]}"
