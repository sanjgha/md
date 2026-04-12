"""FastAPI dependency functions shared across routes."""

import logging
from functools import lru_cache
from typing import Generator

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session, sessionmaker

from src.config import get_config
from src.db.connection import get_engine
from src.db.models import User

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _session_factory() -> sessionmaker:
    """Cache session factory — created once per process."""
    config = get_config()
    engine = get_engine(config.DATABASE_URL)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session; close on exit."""
    db: Session = _session_factory()()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session) -> User:
    """Resolve request.state.user_id → User row. Raises 401 if missing/invalid.

    NOTE: db is NOT a Depends() here — callers must inject it.
    Routes use: user: User = Depends(get_current_user_dep)
    """
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    user = db.get(User, user_id)
    if user is None:
        logger.warning("Session references missing user_id=%s", user_id)
        raise HTTPException(status_code=401, detail="user not found")
    return user
