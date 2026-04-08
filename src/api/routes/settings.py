"""GET/PUT routes for user UI settings.

GET /api/settings — return all ui_settings for current user.
PUT /api/settings — upsert provided keys; return full settings.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db
from src.api.schemas import SettingsOut, SettingsPatch
from src.db.models import UiSetting, User

router = APIRouter()


def _current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Resolve authenticated user from request.state.user_id."""
    return get_current_user(request, db)


def _load_settings(db: Session, user_id: int) -> SettingsOut:
    """Load all UI settings for user; supply defaults if missing."""
    rows = db.execute(select(UiSetting).where(UiSetting.user_id == user_id)).scalars().all()
    kv = {row.key: row.value for row in rows}
    return SettingsOut(
        theme=kv.get("theme", "dark"),
        timezone=kv.get("timezone", "America/New_York"),
    )


@router.get("", response_model=SettingsOut)
def get_settings(user: User = Depends(_current_user), db: Session = Depends(get_db)):
    """Return all UI settings for the authenticated user."""
    return _load_settings(db, user.id)


@router.put("", response_model=SettingsOut)
def put_settings(
    body: SettingsPatch,
    user: User = Depends(_current_user),
    db: Session = Depends(get_db),
):
    """Upsert UI settings; return full settings (including defaults for unset keys)."""
    updates = body.model_dump(exclude_none=True)
    for key, value in updates.items():
        stmt = (
            pg_insert(UiSetting)
            .values(user_id=user.id, key=key, value=value)
            .on_conflict_do_update(
                index_elements=["user_id", "key"],
                set_={"value": value},
            )
        )
        db.execute(stmt)
    db.commit()
    return _load_settings(db, user.id)
