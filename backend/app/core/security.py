"""
security.py - Passwords, login tokens and rate limits.

Used by: app/core/auth.py, app/routes/auth_routes.py, main.py
"""
import re
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import HTTPException, Request

from app import config


# ---------------------------------------------------------------------------
# Passwords (bcrypt is slow on purpose, so stolen hashes are useless)
# ---------------------------------------------------------------------------
def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def temporary_password() -> str:
    """A random password an admin gives to a user; the user must change it at the next login."""
    import secrets
    return "Rg-" + secrets.token_urlsafe(9) + "7"


def check_password_rules(password: str) -> None:
    """Reject weak passwords with a clear message."""
    if len(password) < config.PASSWORD_MIN_LENGTH:
        raise HTTPException(400, f"Password must be at least {config.PASSWORD_MIN_LENGTH} characters.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise HTTPException(400, "Password must contain at least one letter and one number.")


# ---------------------------------------------------------------------------
# Login tokens (JWT)
# ---------------------------------------------------------------------------
def create_token(user_id: int, email: str, role: str, token_version: int = 0) -> str:
    """token_version ("tv") goes up when the password changes -> all older tokens stop working."""
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "tv": token_version,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=config.ACCESS_TOKEN_MINUTES),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Check the signature and expiry. Raises 401 if anything is wrong."""
    try:
        return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid session. Please log in again.")


# ---------------------------------------------------------------------------
# Rate limiting (stops password guessing and request flooding)
# ---------------------------------------------------------------------------
class RateLimiter:
    """Remembers request times per key and refuses when there are too many in the window."""

    def __init__(self):
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, max_requests: int, per_seconds: int) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > per_seconds:
                hits.popleft()
            if len(hits) >= max_requests:
                return False
            hits.append(now)
            return True


rate_limiter = RateLimiter()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request, name: str, limit: tuple) -> None:
    max_requests, per_seconds = limit
    if not rate_limiter.hit(f"{name}:{client_ip(request)}", max_requests, per_seconds):
        raise HTTPException(429, "Too many requests. Please wait a minute and try again.")
