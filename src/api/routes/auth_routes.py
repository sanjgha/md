"""POST /api/auth/login and /api/auth/logout."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.auth import (
    check_rate_limit,
    create_session,
    delete_session,
    record_failure,
    verify_password,
)
from src.api.deps import get_db
from src.api.schemas import LoginRequest
from src.db.models import User

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """Authenticate user with username and password, return session cookie."""
    client_ip = request.client.host if request.client else "unknown"

    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="too many failed attempts, try again later")

    user = db.execute(select(User).where(User.username == body.username)).scalar_one_or_none()
    if user is None or not verify_password(body.password, str(user.password_hash)):
        record_failure(client_ip)
        raise HTTPException(status_code=401, detail="invalid credentials")

    token = create_session(int(user.id))
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="lax",
        path="/",
        # secure=True is enforced by the TLS terminator in prod; omit in dev
    )
    return {"ok": True}


@router.post("/logout")
def logout(request: Request, response: Response):
    """Invalidate the session cookie and logout the user."""
    token = request.cookies.get("session")
    if token:
        delete_session(token)
    response.delete_cookie(key="session", path="/")
    return {"ok": True}
