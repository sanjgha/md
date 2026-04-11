"""Session-based auth: in-memory session store, password hashing, rate limiter, middleware."""

import secrets
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

SESSION_TTL = timedelta(hours=12)
RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_WINDOW_SECS = 60
RATE_LIMIT_LOCKOUT_SECS = 60


@dataclass
class SessionData:
    """Session data container."""

    user_id: int
    expires_at: datetime


# Module-level stores (lost on process restart by design — see spec §11)
SESSIONS: dict[str, SessionData] = {}
_rate_failures: dict[str, list[float]] = defaultdict(list)
_lockouts: dict[str, float] = {}  # ip → lockout_until epoch


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Return True if password matches the bcrypt hash (constant-time)."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


def create_session(user_id: int) -> str:
    """Create a new session token for user_id. Returns the opaque token."""
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = SessionData(
        user_id=user_id,
        expires_at=datetime.utcnow() + SESSION_TTL,
    )
    return token


def get_session(token: str) -> Optional[SessionData]:
    """Look up an active session by token. Removes expired sessions lazily."""
    session = SESSIONS.get(token)
    if session is None:
        return None
    if datetime.utcnow() > session.expires_at:
        del SESSIONS[token]
        return None
    return session


def delete_session(token: str) -> None:
    """Invalidate a session (logout)."""
    SESSIONS.pop(token, None)


def check_rate_limit(ip: str) -> bool:
    """Return True if this IP is allowed to attempt login; False if locked out."""
    now = time.time()
    if now < _lockouts.get(ip, 0):
        return False
    # Prune failures outside the rolling window
    _rate_failures[ip] = [t for t in _rate_failures[ip] if now - t < RATE_LIMIT_WINDOW_SECS]
    return len(_rate_failures[ip]) < RATE_LIMIT_MAX_ATTEMPTS


def record_failure(ip: str) -> None:
    """Record a failed login attempt; lock out the IP after threshold."""
    now = time.time()
    _rate_failures[ip].append(now)
    if len(_rate_failures[ip]) >= RATE_LIMIT_MAX_ATTEMPTS:
        _lockouts[ip] = now + RATE_LIMIT_LOCKOUT_SECS


class SessionMiddleware(BaseHTTPMiddleware):
    """Read the session cookie on every request; attach user_id to request.state."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process the request and attach session data if available."""
        token = request.cookies.get("session")
        if token:
            session = get_session(token)
            if session:
                request.state.user_id = session.user_id
        return await call_next(request)
