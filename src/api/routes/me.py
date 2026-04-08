"""GET /api/me — return the authenticated user."""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db
from src.api.schemas import UserOut
from src.db.models import User

router = APIRouter()


def _current_user(request: Request, db: Session = Depends(get_db)) -> User:
    return get_current_user(request, db)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(_current_user)):
    """Return the currently authenticated user."""
    return user
