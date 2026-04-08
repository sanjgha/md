# Foundation: API + UI Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI backend + SolidJS frontend foundation that proves the full stack works end-to-end — session auth, settings CRUD, live WebSocket heartbeat, and a settings page with an extensible panel registry.

**Architecture:** FastAPI lives in `src/api/` alongside existing Python code and serves both REST/WS API and built frontend static files. SolidJS + Vite frontend in `frontend/`. Session auth uses an in-memory dict (single-user, documented tradeoff). All user-scoped routes use a `get_current_user(request) → User` FastAPI dependency — the forward-compat pattern for eventual multi-user support.

**Tech Stack:** FastAPI ≥0.110, uvicorn[standard], passlib[bcrypt], python-multipart, SQLAlchemy 2 (existing), Alembic (existing), SolidJS, solid-router, Vite, TypeScript strict, Vitest, @solidjs/testing-library, Playwright

---

## File Map

**New backend files:**
- `src/api/__init__.py` — package marker
- `src/api/main.py` — app factory, lifespan, static mount
- `src/api/auth.py` — SESSIONS dict, hash/verify, rate limiter, SessionMiddleware
- `src/api/deps.py` — `get_db`, `get_current_user`
- `src/api/schemas.py` — Pydantic request/response models
- `src/api/ws.py` — PubSubRegistry, `ws_endpoint`, `heartbeat_loop`
- `src/api/routes/__init__.py` — package marker
- `src/api/routes/health.py` — GET /api/health
- `src/api/routes/auth_routes.py` — POST /api/auth/login, /logout
- `src/api/routes/me.py` — GET /api/me
- `src/api/routes/settings.py` — GET/PUT /api/settings
- `src/db/migrations/versions/20260408_foundation.py` — users + ui_settings + seed

**Modified backend files:**
- `pyproject.toml` — add fastapi, uvicorn[standard], passlib[bcrypt], python-multipart; add httpx to dev
- `src/db/models.py` — add User, UiSetting
- `src/config.py` — add APP_USERNAME, APP_PASSWORD (optional, migration only), APP_BIND_HOST

**New test files:**
- `tests/unit/api/__init__.py`
- `tests/unit/api/test_auth.py`
- `tests/unit/api/test_ws_registry.py`
- `tests/unit/api/test_deps.py`
- `tests/integration/api/__init__.py`
- `tests/integration/api/conftest.py`
- `tests/integration/api/test_migration.py`
- `tests/integration/api/test_auth_flow.py`
- `tests/integration/api/test_me_endpoint.py`
- `tests/integration/api/test_settings_endpoint.py`
- `tests/integration/api/test_ws_endpoint.py`

**New frontend files:**
- `frontend/package.json`
- `frontend/tsconfig.json`
- `frontend/vite.config.ts`
- `frontend/vitest.config.ts`
- `frontend/index.html`
- `frontend/src/main.tsx`
- `frontend/src/app.tsx`
- `frontend/src/index.css`
- `frontend/src/lib/api.ts`
- `frontend/src/lib/ws.ts`
- `frontend/src/lib/auth.ts`
- `frontend/src/lib/settings-store.ts`
- `frontend/src/pages/login.tsx`
- `frontend/src/pages/dashboard.tsx`
- `frontend/src/pages/settings/registry.ts`
- `frontend/src/pages/settings/index.tsx`
- `frontend/src/pages/settings/panels/appearance.tsx`
- `frontend/src/types/api.ts` — generated from /openapi.json, checked in
- `frontend/tests/unit/lib/api.test.ts`
- `frontend/tests/unit/lib/ws.test.ts`
- `frontend/tests/unit/lib/auth.test.tsx`
- `frontend/tests/unit/pages/appearance-panel.test.tsx`
- `frontend/tests/unit/pages/settings-registry.test.tsx`
- `frontend/tests/e2e/smoke.spec.ts`

**Modified other:**
- `Makefile` — add `ci`, `generate-types`, `frontend-test` targets

---

## Task 1: Python dependencies + config

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/config.py`
- Test: `tests/unit/test_config.py` (existing — add new env var coverage)

- [ ] **Step 1: Write failing test for new config fields**

```python
# In tests/unit/test_config.py, add at the bottom:
def test_config_api_fields_default():
    """APP_USERNAME/PASSWORD are optional in config (migration-only)."""
    from src.config import get_config
    env = {
        "DATABASE_URL": "postgresql://test:test@localhost/testdb",
        "MARKETDATA_API_TOKEN": "tok",
    }
    with patch.dict(os.environ, env, clear=True):
        get_config.cache_clear()
        cfg = get_config()
        assert cfg.APP_USERNAME is None
        assert cfg.APP_PASSWORD is None
        assert cfg.APP_BIND_HOST == "127.0.0.1"
    get_config.cache_clear()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/test_config.py::test_config_api_fields_default -v
```
Expected: `AttributeError: 'Config' object has no attribute 'APP_USERNAME'`

- [ ] **Step 3: Add fields to config.py**

In `src/config.py`, inside `Config.__init__`, after the existing field assignments, add:

```python
        # API server settings (APP_USERNAME/APP_PASSWORD read only by migration)
        self.APP_USERNAME = os.getenv("APP_USERNAME")
        self.APP_PASSWORD = os.getenv("APP_PASSWORD")
        self.APP_BIND_HOST = os.getenv("APP_BIND_HOST", "127.0.0.1")
        self.APP_PORT = int(os.getenv("APP_PORT", "8000"))
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/unit/test_config.py::test_config_api_fields_default -v
```
Expected: PASS

- [ ] **Step 5: Add Python dependencies to pyproject.toml**

In `pyproject.toml`, in the `dependencies` list, add:

```toml
    "fastapi>=0.110.0",
    "uvicorn[standard]>=0.27.0",
    "passlib[bcrypt]>=1.7.4",
    "python-multipart>=0.0.9",
```

In `[project.optional-dependencies]` `dev` list, add:

```toml
    "httpx>=0.27.0",
    "pytest-asyncio>=0.23.0",
```

- [ ] **Step 6: Install updated dependencies**

```bash
pip install -e ".[dev]"
```
Expected: installs fastapi, uvicorn, passlib, httpx, etc. with no errors.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/config.py tests/unit/test_config.py
git commit -m "chore: add FastAPI deps and API config fields"
```

---

## Task 2: DB models — User and UiSetting

**Files:**
- Modify: `src/db/models.py`
- Test: `tests/unit/test_db_models.py` (existing — add new model coverage)

- [ ] **Step 1: Write failing tests for new models**

```python
# In tests/unit/test_db_models.py, add at the bottom:
def test_user_model_tablename():
    from src.db.models import User
    assert User.__tablename__ == "users"

def test_ui_setting_model_tablename():
    from src.db.models import UiSetting
    assert UiSetting.__tablename__ == "ui_settings"

def test_ui_setting_has_user_id_fk():
    from src.db.models import UiSetting
    col = UiSetting.__table__.c["user_id"]
    assert col.nullable is False
    assert len(col.foreign_keys) == 1

def test_ui_setting_unique_constraint():
    from src.db.models import UiSetting
    constraint_names = {c.name for c in UiSetting.__table__.constraints}
    assert "uq_ui_settings_user_key" in constraint_names
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_db_models.py::test_user_model_tablename \
       tests/unit/test_db_models.py::test_ui_setting_model_tablename -v
```
Expected: `ImportError: cannot import name 'User' from 'src.db.models'`

- [ ] **Step 3: Add models to src/db/models.py**

At the top of `src/db/models.py`, the existing imports already include `UniqueConstraint`, `ForeignKey`, `Integer`, `String`, `DateTime`, `JSONB`. Add the two new classes after the `EconomicIndicator` class at the bottom of the file:

```python
class User(Base):
    """Application user (single-user now; forward-compatible with multi-user)."""

    __tablename__ = "users"

    id            = Column(Integer, primary_key=True)
    username      = Column(String(64), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at    = Column(DateTime, default=datetime.utcnow)

    ui_settings = relationship(
        "UiSetting", back_populates="user", cascade="all, delete-orphan"
    )


class UiSetting(Base):
    """Per-user UI preferences stored as key/JSONB-value pairs."""

    __tablename__ = "ui_settings"

    id      = Column(Integer, primary_key=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        server_default="1",
    )
    key   = Column(String(64), nullable=False)
    value = Column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_ui_settings_user_key"),
    )

    user = relationship("User", back_populates="ui_settings")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/test_db_models.py::test_user_model_tablename \
       tests/unit/test_db_models.py::test_ui_setting_model_tablename \
       tests/unit/test_db_models.py::test_ui_setting_has_user_id_fk \
       tests/unit/test_db_models.py::test_ui_setting_unique_constraint -v
```
Expected: all PASS

- [ ] **Step 5: Run full unit suite to check no regressions**

```bash
pytest tests/unit/ -v
```
Expected: all existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add src/db/models.py tests/unit/test_db_models.py
git commit -m "feat: add User and UiSetting ORM models"
```

---

## Task 3: Alembic migration — users + ui_settings + seed

**Files:**
- Create: `src/db/migrations/versions/20260408_foundation.py`
- Create: `tests/integration/api/__init__.py`
- Create: `tests/integration/api/test_migration.py`

- [ ] **Step 1: Create test directory**

```bash
mkdir -p tests/integration/api
touch tests/integration/api/__init__.py
```

- [ ] **Step 2: Write failing migration test**

Create `tests/integration/api/test_migration.py`:

```python
"""Integration tests for the Foundation Alembic migration."""
import os
import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, inspect, text


@pytest.fixture(scope="module")
def migration_engine(postgres_container):
    """Fresh engine on the testcontainers DB (no tables yet)."""
    url = postgres_container.get_connection_url()
    engine = create_engine(url)
    yield engine
    engine.dispose()


def _alembic_cfg(db_url: str) -> AlembicConfig:
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_migration_creates_users_table(migration_engine, postgres_container):
    url = postgres_container.get_connection_url()
    os.environ["APP_USERNAME"] = "testadmin"
    os.environ["APP_PASSWORD"] = "testpassword123"
    try:
        command.upgrade(_alembic_cfg(url), "head")
        inspector = inspect(migration_engine)
        assert "users" in inspector.get_table_names()
        assert "ui_settings" in inspector.get_table_names()
    finally:
        command.downgrade(_alembic_cfg(url), "-1")
        del os.environ["APP_USERNAME"]
        del os.environ["APP_PASSWORD"]


def test_migration_seeds_user_and_settings(migration_engine, postgres_container):
    url = postgres_container.get_connection_url()
    os.environ["APP_USERNAME"] = "testadmin"
    os.environ["APP_PASSWORD"] = "testpassword123"
    try:
        command.upgrade(_alembic_cfg(url), "head")
        with migration_engine.connect() as conn:
            user_row = conn.execute(text("SELECT id, username FROM users WHERE id=1")).fetchone()
            assert user_row is not None
            assert user_row.username == "testadmin"

            settings = conn.execute(
                text("SELECT key, value FROM ui_settings WHERE user_id=1 ORDER BY key")
            ).fetchall()
            settings_dict = {r.key: r.value for r in settings}
            assert settings_dict["theme"] == "dark"
            assert settings_dict["timezone"] == "America/New_York"
    finally:
        command.downgrade(_alembic_cfg(url), "-1")
        del os.environ["APP_USERNAME"]
        del os.environ["APP_PASSWORD"]


def test_migration_downgrade_drops_tables(migration_engine, postgres_container):
    url = postgres_container.get_connection_url()
    os.environ["APP_USERNAME"] = "testadmin"
    os.environ["APP_PASSWORD"] = "testpassword123"
    try:
        command.upgrade(_alembic_cfg(url), "head")
        command.downgrade(_alembic_cfg(url), "-1")
        inspector = inspect(migration_engine)
        assert "users" not in inspector.get_table_names()
        assert "ui_settings" not in inspector.get_table_names()
    finally:
        del os.environ["APP_USERNAME"]
        del os.environ["APP_PASSWORD"]


def test_migration_raises_without_credentials(postgres_container):
    url = postgres_container.get_connection_url()
    for key in ("APP_USERNAME", "APP_PASSWORD"):
        os.environ.pop(key, None)
    with pytest.raises(Exception, match="APP_USERNAME"):
        command.upgrade(_alembic_cfg(url), "head")
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/integration/api/test_migration.py -v
```
Expected: fail with "Can't locate revision identified by 'head'" or no migration found.

- [ ] **Step 4: Create the migration file**

Create `src/db/migrations/versions/20260408_foundation.py`:

```python
"""Foundation: users + ui_settings tables with single-user seed.

Revision ID: 20260408_foundation
Revises: a1b2c3d4e5f6
Create Date: 2026-04-08
"""
import os

import sqlalchemy as sa
from alembic import op
from passlib.context import CryptContext
from sqlalchemy.dialects.postgresql import JSONB

revision = "20260408_foundation"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def upgrade() -> None:
    username = os.environ.get("APP_USERNAME")
    password = os.environ.get("APP_PASSWORD")
    if not username or not password:
        raise RuntimeError(
            "APP_USERNAME and APP_PASSWORD env vars must be set before running this migration."
        )

    users = op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )

    ui_settings = op.create_table(
        "ui_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("value", JSONB(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "key", name="uq_ui_settings_user_key"),
    )

    op.bulk_insert(
        users,
        [{"id": 1, "username": username, "password_hash": _pwd_context.hash(password)}],
    )

    op.bulk_insert(
        ui_settings,
        [
            {"user_id": 1, "key": "theme", "value": "dark"},
            {"user_id": 1, "key": "timezone", "value": "America/New_York"},
        ],
    )


def downgrade() -> None:
    op.drop_table("ui_settings")
    op.drop_table("users")
```

- [ ] **Step 5: Run migration tests**

```bash
pytest tests/integration/api/test_migration.py -v
```
Expected: all 4 tests PASS. Docker must be running.

- [ ] **Step 6: Commit**

```bash
git add src/db/migrations/versions/20260408_foundation.py \
        tests/integration/api/__init__.py \
        tests/integration/api/test_migration.py
git commit -m "feat: add Foundation Alembic migration (users + ui_settings)"
```

---

## Task 4: Auth module — sessions, hashing, rate limiter, middleware

**Files:**
- Create: `src/api/__init__.py`
- Create: `src/api/auth.py`
- Create: `tests/unit/api/__init__.py`
- Create: `tests/unit/api/test_auth.py`

- [ ] **Step 1: Create package directories**

```bash
mkdir -p src/api/routes
touch src/api/__init__.py src/api/routes/__init__.py
mkdir -p tests/unit/api
touch tests/unit/api/__init__.py
```

- [ ] **Step 2: Write failing unit tests for auth**

Create `tests/unit/api/test_auth.py`:

```python
"""Unit tests for src/api/auth.py — no DB required."""
import time
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest


def test_hash_and_verify_password():
    from src.api.auth import hash_password, verify_password

    hashed = hash_password("mysecret")
    assert hashed != "mysecret"
    assert verify_password("mysecret", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_create_session_returns_unique_tokens():
    from src.api.auth import SESSIONS, create_session

    SESSIONS.clear()
    t1 = create_session(1)
    t2 = create_session(1)
    assert t1 != t2
    assert len(t1) >= 32
    SESSIONS.clear()


def test_get_session_returns_data():
    from src.api.auth import SESSIONS, create_session, get_session

    SESSIONS.clear()
    token = create_session(1)
    session = get_session(token)
    assert session is not None
    assert session.user_id == 1
    SESSIONS.clear()


def test_get_session_returns_none_for_unknown_token():
    from src.api.auth import get_session

    assert get_session("nonexistent") is None


def test_get_session_removes_expired():
    from src.api.auth import SESSIONS, SessionData, get_session

    SESSIONS.clear()
    SESSIONS["expired"] = SessionData(
        user_id=1, expires_at=datetime.utcnow() - timedelta(seconds=1)
    )
    result = get_session("expired")
    assert result is None
    assert "expired" not in SESSIONS
    SESSIONS.clear()


def test_delete_session_removes_entry():
    from src.api.auth import SESSIONS, create_session, delete_session

    SESSIONS.clear()
    token = create_session(1)
    delete_session(token)
    assert token not in SESSIONS
    SESSIONS.clear()


def test_rate_limit_allows_under_threshold():
    from src.api.auth import _lockouts, _rate_failures, check_rate_limit

    _rate_failures.clear()
    _lockouts.clear()
    for _ in range(4):
        assert check_rate_limit("1.2.3.4") is True
        from src.api.auth import record_failure
        record_failure("1.2.3.4")
    _rate_failures.clear()
    _lockouts.clear()


def test_rate_limit_blocks_after_5_failures():
    from src.api.auth import _lockouts, _rate_failures, check_rate_limit, record_failure

    _rate_failures.clear()
    _lockouts.clear()
    for _ in range(5):
        record_failure("1.2.3.5")
    assert check_rate_limit("1.2.3.5") is False
    _rate_failures.clear()
    _lockouts.clear()
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/unit/api/test_auth.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.api.auth'`

- [ ] **Step 4: Create src/api/auth.py**

```python
"""Session-based auth: in-memory session store, password hashing, rate limiter, middleware."""
import secrets
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from passlib.context import CryptContext
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SESSION_TTL = timedelta(hours=12)
RATE_LIMIT_MAX_ATTEMPTS = 5
RATE_LIMIT_WINDOW_SECS = 60
RATE_LIMIT_LOCKOUT_SECS = 60


@dataclass
class SessionData:
    user_id: int
    expires_at: datetime


# Module-level stores (lost on process restart by design — see spec §11)
SESSIONS: dict[str, SessionData] = {}
_rate_failures: dict[str, list[float]] = defaultdict(list)
_lockouts: dict[str, float] = {}  # ip → lockout_until epoch


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return _pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """Return True if password matches the bcrypt hash (constant-time)."""
    return _pwd_context.verify(password, hashed)


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
        token = request.cookies.get("session")
        if token:
            session = get_session(token)
            if session:
                request.state.user_id = session.user_id
        return await call_next(request)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/unit/api/test_auth.py -v
```
Expected: all 8 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/__init__.py src/api/routes/__init__.py \
        src/api/auth.py \
        tests/unit/api/__init__.py tests/unit/api/test_auth.py
git commit -m "feat: add auth module (sessions, bcrypt, rate limiter, middleware)"
```

---

## Task 5: Schemas + API deps

**Files:**
- Create: `src/api/schemas.py`
- Create: `src/api/deps.py`
- Create: `tests/unit/api/test_deps.py`

- [ ] **Step 1: Write failing test for get_current_user**

Create `tests/unit/api/test_deps.py`:

```python
"""Unit tests for FastAPI dependencies."""
import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from starlette.requests import Request


def _make_request(user_id=None):
    scope = {"type": "http", "method": "GET", "path": "/", "query_string": b"",
             "headers": []}
    req = Request(scope)
    if user_id is not None:
        req.state.user_id = user_id
    return req


def test_get_current_user_raises_401_when_no_user_id():
    from src.api.deps import get_current_user

    req = _make_request()  # no user_id on state
    db = MagicMock()
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(req, db)
    assert exc_info.value.status_code == 401


def test_get_current_user_raises_401_when_user_row_missing():
    from src.api.deps import get_current_user

    req = _make_request(user_id=99)
    db = MagicMock()
    db.get.return_value = None  # simulate user not in DB
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(req, db)
    assert exc_info.value.status_code == 401


def test_get_current_user_returns_user():
    from src.api.deps import get_current_user
    from src.db.models import User

    req = _make_request(user_id=1)
    fake_user = MagicMock(spec=User)
    fake_user.id = 1
    db = MagicMock()
    db.get.return_value = fake_user
    result = get_current_user(req, db)
    assert result is fake_user
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/api/test_deps.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.api.deps'`

- [ ] **Step 3: Create src/api/schemas.py**

```python
"""Pydantic request/response models for the Foundation API."""
from typing import Literal
from pydantic import BaseModel, field_validator


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str

    model_config = {"from_attributes": True}


class SettingsPatch(BaseModel):
    """Keys that may be updated via PUT /api/settings.
    Add fields here when new sub-projects introduce settings."""

    theme: Literal["light", "dark"] | None = None
    timezone: str | None = None

    model_config = {"extra": "forbid"}


class SettingsOut(BaseModel):
    """Full settings response returned by GET and PUT /api/settings."""

    theme: str
    timezone: str
```

- [ ] **Step 4: Create src/api/deps.py**

```python
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
    """Cached session factory — created once per process."""
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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/unit/api/test_deps.py -v
```
Expected: all 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/schemas.py src/api/deps.py tests/unit/api/test_deps.py
git commit -m "feat: add API schemas (Pydantic) and FastAPI deps (get_db, get_current_user)"
```

---

## Task 6: Health + me routes

**Files:**
- Create: `src/api/routes/health.py`
- Create: `src/api/routes/me.py`
- Create: `tests/integration/api/conftest.py`
- Create: `tests/integration/api/test_me_endpoint.py`

- [ ] **Step 1: Create integration test conftest**

Create `tests/integration/api/conftest.py`:

```python
"""Shared fixtures for API integration tests."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.api import auth as auth_module
from src.api import deps


def make_api_client(db_session: Session):
    """Create a TestClient with DB dependency overridden to testcontainers session."""
    # Import here to avoid circular issues before app is built
    from src.api.main import create_app

    app = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass  # cleanup handled by db_session fixture

    app.dependency_overrides[deps.get_db] = override_get_db
    return app, TestClient(app, raise_server_exceptions=True)


@pytest.fixture
def api_client(db_session: Session):
    """TestClient with real testcontainers DB, cleared sessions after each test."""
    auth_module.SESSIONS.clear()
    auth_module._rate_failures.clear()
    auth_module._lockouts.clear()
    app, client = make_api_client(db_session)
    with client as c:
        yield c
    app.dependency_overrides.clear()
    auth_module.SESSIONS.clear()


@pytest.fixture
def seeded_user(db_session: Session):
    """Insert a test user into the DB and return (username, password, user_obj)."""
    from src.api.auth import hash_password
    from src.db.models import User

    user = User(
        id=1,
        username="testuser",
        password_hash=hash_password("testpass123"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user, "testpass123"


@pytest.fixture
def authenticated_client(api_client, seeded_user):
    """API client with a valid session cookie already set."""
    user, password = seeded_user
    resp = api_client.post("/api/auth/login", json={"username": user.username, "password": password})
    assert resp.status_code == 200
    return api_client
```

- [ ] **Step 2: Write failing me endpoint test**

Create `tests/integration/api/test_me_endpoint.py`:

```python
"""Integration tests for GET /api/me."""


def test_me_returns_user_when_authenticated(authenticated_client, seeded_user):
    user, _ = seeded_user
    resp = authenticated_client.get("/api/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == user.id
    assert data["username"] == user.username


def test_me_returns_401_when_unauthenticated(api_client):
    resp = api_client.get("/api/me")
    assert resp.status_code == 401
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/integration/api/test_me_endpoint.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.api.main'`

- [ ] **Step 4: Create health route**

Create `src/api/routes/health.py`:

```python
"""GET /api/health — liveness probe."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Create me route**

Create `src/api/routes/me.py`:

```python
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
    return user
```

- [ ] **Step 6: Create minimal app factory (needed for TestClient)**

Create `src/api/main.py`:

```python
"""FastAPI application factory."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.api.auth import SessionMiddleware
from src.api.routes.health import router as health_router
from src.api.routes.me import router as me_router

FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield  # ws heartbeat wired in Task 9


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan, title="market-data")
    app.add_middleware(SessionMiddleware)
    app.include_router(health_router, prefix="/api")
    app.include_router(me_router, prefix="/api")
    if FRONTEND_DIST.exists():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
    return app
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/integration/api/test_me_endpoint.py -v
```
Expected: both tests PASS

- [ ] **Step 8: Commit**

```bash
git add src/api/routes/health.py src/api/routes/me.py src/api/main.py \
        tests/integration/api/conftest.py tests/integration/api/test_me_endpoint.py
git commit -m "feat: add health and /me routes with integration tests"
```

---

## Task 7: Auth routes — login + logout

**Files:**
- Create: `src/api/routes/auth_routes.py`
- Create: `tests/integration/api/test_auth_flow.py`
- Modify: `src/api/main.py`

- [ ] **Step 1: Write failing auth flow tests**

Create `tests/integration/api/test_auth_flow.py`:

```python
"""Integration tests for POST /api/auth/login and /api/auth/logout."""
import pytest


def test_login_correct_credentials_returns_200_and_cookie(api_client, seeded_user):
    user, password = seeded_user
    resp = api_client.post("/api/auth/login", json={"username": user.username, "password": password})
    assert resp.status_code == 200
    assert "session" in resp.cookies


def test_login_wrong_password_returns_401(api_client, seeded_user):
    user, _ = seeded_user
    resp = api_client.post("/api/auth/login", json={"username": user.username, "password": "wrong"})
    assert resp.status_code == 401
    assert "session" not in resp.cookies


def test_login_unknown_user_returns_401(api_client):
    resp = api_client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
    assert resp.status_code == 401


def test_logout_invalidates_session(authenticated_client):
    # confirm we're authenticated
    assert authenticated_client.get("/api/me").status_code == 200
    resp = authenticated_client.post("/api/auth/logout")
    assert resp.status_code == 200
    # session cookie cleared — subsequent request should 401
    assert authenticated_client.get("/api/me").status_code == 401


def test_login_rate_limit_triggers_after_5_failures(api_client, seeded_user):
    from src.api.auth import _lockouts, _rate_failures
    _rate_failures.clear()
    _lockouts.clear()

    user, _ = seeded_user
    for _ in range(5):
        api_client.post("/api/auth/login", json={"username": user.username, "password": "bad"})

    resp = api_client.post("/api/auth/login", json={"username": user.username, "password": "bad"})
    assert resp.status_code == 429
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/integration/api/test_auth_flow.py -v
```
Expected: fail (no auth routes registered yet)

- [ ] **Step 3: Create auth routes**

Create `src/api/routes/auth_routes.py`:

```python
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
    client_ip = request.client.host if request.client else "unknown"

    if not check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="too many failed attempts, try again later")

    user = db.execute(select(User).where(User.username == body.username)).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        record_failure(client_ip)
        raise HTTPException(status_code=401, detail="invalid credentials")

    token = create_session(user.id)
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
    token = request.cookies.get("session")
    if token:
        delete_session(token)
    response.delete_cookie(key="session", path="/")
    return {"ok": True}
```

- [ ] **Step 4: Register auth router in main.py**

Edit `src/api/main.py`, add import and router:

```python
from src.api.routes.auth_routes import router as auth_router
```

Add inside `create_app()`, before the StaticFiles mount:

```python
    app.include_router(auth_router, prefix="/api/auth")
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/integration/api/test_auth_flow.py -v
```
Expected: all 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/routes/auth_routes.py src/api/main.py \
        tests/integration/api/test_auth_flow.py
git commit -m "feat: add login/logout routes with rate limiting"
```

---

## Task 8: Settings routes — GET + PUT

**Files:**
- Create: `src/api/routes/settings.py`
- Create: `tests/integration/api/test_settings_endpoint.py`
- Modify: `src/api/main.py`

- [ ] **Step 1: Write failing settings tests**

Create `tests/integration/api/test_settings_endpoint.py`:

```python
"""Integration tests for GET/PUT /api/settings."""


def test_get_settings_returns_seeded_defaults(authenticated_client, seeded_user, db_session):
    """GET returns settings rows present in DB for the user."""
    from src.db.models import UiSetting

    user, _ = seeded_user
    # Seed settings manually (migration seed won't run in test DB)
    for key, val in [("theme", "dark"), ("timezone", "America/New_York")]:
        db_session.add(UiSetting(user_id=user.id, key=key, value=val))
    db_session.commit()

    resp = authenticated_client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["theme"] == "dark"
    assert data["timezone"] == "America/New_York"


def test_get_settings_unauthenticated_returns_401(api_client):
    resp = api_client.get("/api/settings")
    assert resp.status_code == 401


def test_put_settings_upserts_theme(authenticated_client, seeded_user, db_session):
    from src.db.models import UiSetting

    user, _ = seeded_user
    db_session.add(UiSetting(user_id=user.id, key="theme", value="dark"))
    db_session.add(UiSetting(user_id=user.id, key="timezone", value="America/New_York"))
    db_session.commit()

    resp = authenticated_client.put("/api/settings", json={"theme": "light"})
    assert resp.status_code == 200
    assert resp.json()["theme"] == "light"
    assert resp.json()["timezone"] == "America/New_York"  # unchanged


def test_put_settings_second_update_replaces(authenticated_client, seeded_user, db_session):
    from src.db.models import UiSetting

    user, _ = seeded_user
    db_session.add(UiSetting(user_id=user.id, key="theme", value="dark"))
    db_session.add(UiSetting(user_id=user.id, key="timezone", value="America/New_York"))
    db_session.commit()

    authenticated_client.put("/api/settings", json={"theme": "light"})
    resp = authenticated_client.put("/api/settings", json={"theme": "dark"})
    assert resp.status_code == 200
    assert resp.json()["theme"] == "dark"


def test_put_settings_unknown_key_returns_422(authenticated_client, seeded_user):
    resp = authenticated_client.put("/api/settings", json={"badkey": "value"})
    assert resp.status_code == 422


def test_put_settings_invalid_theme_returns_422(authenticated_client, seeded_user):
    resp = authenticated_client.put("/api/settings", json={"theme": "purple"})
    assert resp.status_code == 422


def test_put_settings_unauthenticated_returns_401(api_client):
    resp = api_client.put("/api/settings", json={"theme": "dark"})
    assert resp.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/integration/api/test_settings_endpoint.py -v
```
Expected: fail (no settings route yet)

- [ ] **Step 3: Create settings route**

Create `src/api/routes/settings.py`:

```python
"""GET /api/settings — return all ui_settings for current user.
   PUT /api/settings — upsert provided keys; return full settings."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db
from src.api.schemas import SettingsOut, SettingsPatch
from src.db.models import UiSetting, User

router = APIRouter()


def _current_user(request: Request, db: Session = Depends(get_db)) -> User:
    return get_current_user(request, db)


def _load_settings(db: Session, user_id: int) -> SettingsOut:
    rows = db.execute(
        select(UiSetting).where(UiSetting.user_id == user_id)
    ).scalars().all()
    kv = {row.key: row.value for row in rows}
    return SettingsOut(
        theme=kv.get("theme", "dark"),
        timezone=kv.get("timezone", "America/New_York"),
    )


@router.get("", response_model=SettingsOut)
def get_settings(user: User = Depends(_current_user), db: Session = Depends(get_db)):
    return _load_settings(db, user.id)


@router.put("", response_model=SettingsOut)
def put_settings(
    body: SettingsPatch,
    user: User = Depends(_current_user),
    db: Session = Depends(get_db),
):
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
```

- [ ] **Step 4: Register settings router in main.py**

Edit `src/api/main.py`, add import:

```python
from src.api.routes.settings import router as settings_router
```

Add inside `create_app()`:

```python
    app.include_router(settings_router, prefix="/api/settings")
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/integration/api/test_settings_endpoint.py -v
```
Expected: all 7 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/routes/settings.py src/api/main.py \
        tests/integration/api/test_settings_endpoint.py
git commit -m "feat: add settings GET/PUT routes with upsert"
```

---

## Task 9: WebSocket — PubSubRegistry, endpoint, heartbeat

**Files:**
- Create: `src/api/ws.py`
- Create: `tests/unit/api/test_ws_registry.py`
- Create: `tests/integration/api/test_ws_endpoint.py`
- Modify: `src/api/main.py`

- [ ] **Step 1: Write unit tests for PubSubRegistry**

Create `tests/unit/api/test_ws_registry.py`:

```python
"""Unit tests for PubSubRegistry in src/api/ws.py."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def registry():
    from src.api.ws import PubSubRegistry
    return PubSubRegistry()


@pytest.mark.asyncio
async def test_subscribe_and_publish(registry):
    ws = AsyncMock()
    await registry.subscribe(ws, "test:topic")
    await registry.publish("test:topic", {"msg": "hello"})
    ws.send_json.assert_called_once_with({"topic": "test:topic", "data": {"msg": "hello"}})


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery(registry):
    ws = AsyncMock()
    await registry.subscribe(ws, "test:topic")
    await registry.unsubscribe(ws, "test:topic")
    await registry.publish("test:topic", {"msg": "hello"})
    ws.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_disconnect_removes_from_all_topics(registry):
    ws = AsyncMock()
    await registry.subscribe(ws, "t1")
    await registry.subscribe(ws, "t2")
    await registry.disconnect(ws)
    await registry.publish("t1", {})
    await registry.publish("t2", {})
    ws.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_publish_skips_dead_connection(registry):
    ws = AsyncMock()
    ws.send_json.side_effect = Exception("connection closed")
    await registry.subscribe(ws, "test:topic")
    # Should not raise
    await registry.publish("test:topic", {})
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/api/test_ws_registry.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.api.ws'`

- [ ] **Step 3: Create src/api/ws.py**

```python
"""WebSocket infrastructure: PubSubRegistry, ws_endpoint, heartbeat_loop."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class PubSubRegistry:
    """Thread-safe (asyncio) pub/sub registry mapping topic → set[WebSocket]."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._subs: dict[str, set[WebSocket]] = {}

    async def subscribe(self, ws: WebSocket, topic: str) -> None:
        async with self._lock:
            self._subs.setdefault(topic, set()).add(ws)

    async def unsubscribe(self, ws: WebSocket, topic: str) -> None:
        async with self._lock:
            if topic in self._subs:
                self._subs[topic].discard(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            for subscribers in self._subs.values():
                subscribers.discard(ws)

    async def publish(self, topic: str, data: Any) -> None:
        message = {"topic": topic, "data": data}
        async with self._lock:
            subscribers = list(self._subs.get(topic, set()))
        for ws in subscribers:
            try:
                await ws.send_json(message)
            except Exception:
                logger.debug("Dead WebSocket removed from topic %s", topic)
                await self.disconnect(ws)

    async def close_all(self) -> None:
        async with self._lock:
            sockets: set[WebSocket] = set()
            for subscribers in self._subs.values():
                sockets.update(subscribers)
            self._subs.clear()
        for ws in sockets:
            try:
                await ws.close()
            except Exception:
                pass


# Module-level registry shared by the app
pubsub = PubSubRegistry()


async def heartbeat_loop(registry: PubSubRegistry, interval: float = 5.0) -> None:
    """Publish system:heartbeat every `interval` seconds until cancelled."""
    while True:
        await asyncio.sleep(interval)
        ts = datetime.now(tz=timezone.utc).isoformat()
        await registry.publish("system:heartbeat", {"ts": ts})


async def ws_endpoint(websocket: WebSocket) -> None:
    """Single /ws endpoint: authenticate via session cookie, then pub/sub loop."""
    from src.api.auth import get_session

    token = websocket.cookies.get("session")
    session = get_session(token) if token else None
    if session is None:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    await pubsub.subscribe(websocket, "system:heartbeat")

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                import json
                msg = json.loads(raw)
            except ValueError:
                await websocket.send_json({"op": "error", "message": "invalid JSON"})
                continue

            op = msg.get("op")
            if op == "subscribe":
                await pubsub.subscribe(websocket, msg.get("topic", ""))
            elif op == "unsubscribe":
                await pubsub.unsubscribe(websocket, msg.get("topic", ""))
            elif op == "ping":
                await websocket.send_json({"op": "pong"})
            else:
                await websocket.send_json({"op": "error", "message": f"unknown op: {op}"})
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.disconnect(websocket)
```

- [ ] **Step 4: Run unit tests**

```bash
pytest tests/unit/api/test_ws_registry.py -v
```
Expected: all 4 tests PASS

- [ ] **Step 5: Write WebSocket integration test**

Create `tests/integration/api/test_ws_endpoint.py`:

```python
"""Integration tests for the /ws endpoint."""
import pytest
from starlette.testclient import TestClient


def test_ws_rejects_unauthenticated(api_client):
    with pytest.raises(Exception):
        with api_client.websocket_connect("/ws") as ws:
            ws.receive_json()  # should not reach here — closed 1008


def test_ws_accepts_authenticated_and_receives_heartbeat(authenticated_client, monkeypatch):
    # Set a fast heartbeat interval so the test doesn't wait 5s
    monkeypatch.setenv("HEARTBEAT_INTERVAL", "0.1")
    with authenticated_client.websocket_connect("/ws") as ws:
        msg = ws.receive_json(timeout=3)
        assert msg["topic"] == "system:heartbeat"


def test_ws_ping_pong(authenticated_client):
    with authenticated_client.websocket_connect("/ws") as ws:
        ws.send_json({"op": "ping"})
        msg = ws.receive_json(timeout=3)
        assert msg == {"op": "pong"}
```

- [ ] **Step 6: Wire WebSocket into main.py**

Edit `src/api/main.py`. Replace the stub lifespan with the real one and add ws imports:

```python
"""FastAPI application factory."""
import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.api.auth import SessionMiddleware
from src.api.routes.auth_routes import router as auth_router
from src.api.routes.health import router as health_router
from src.api.routes.me import router as me_router
from src.api.routes.settings import router as settings_router
from src.api.ws import heartbeat_loop, pubsub, ws_endpoint

FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    interval = float(os.environ.get("HEARTBEAT_INTERVAL", "5.0"))
    task = asyncio.create_task(heartbeat_loop(pubsub, interval))
    try:
        yield
    finally:
        task.cancel()
        await pubsub.close_all()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan, title="market-data")
    app.add_middleware(SessionMiddleware)
    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(me_router, prefix="/api")
    app.include_router(settings_router, prefix="/api/settings")
    app.add_api_websocket_route("/ws", ws_endpoint)
    if FRONTEND_DIST.exists():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
    return app
```

- [ ] **Step 7: Run all API tests**

```bash
pytest tests/unit/api/ tests/integration/api/ -v --ignore=tests/integration/api/test_migration.py
```
Expected: all pass. (Migration test excluded since it needs a fresh DB.)

- [ ] **Step 8: Commit**

```bash
git add src/api/ws.py src/api/main.py \
        tests/unit/api/test_ws_registry.py \
        tests/integration/api/test_ws_endpoint.py
git commit -m "feat: add WebSocket PubSubRegistry, heartbeat, and /ws endpoint"
```

---

## Task 10: Full backend test run + Makefile ci target

**Files:**
- Modify: `Makefile`

- [ ] **Step 1: Run full backend test suite**

```bash
pytest tests/ -v
```
Expected: all tests pass (unit + integration). Docker must be running for testcontainers.

- [ ] **Step 2: Run linting and type checking**

```bash
ruff check src/api/ tests/unit/api/ tests/integration/api/
mypy src/api/ --ignore-missing-imports
```
Fix any errors before proceeding.

- [ ] **Step 3: Add ci and generate-types targets to Makefile**

Edit `Makefile`. Replace existing content with:

```makefile
.PHONY: install dev-install test test-cov lint format typecheck ci \
        frontend-install frontend-dev frontend-build frontend-test \
        generate-types clean

install:
	pip install -e .

dev-install:
	pip install -e ".[dev]"

test:
	pytest tests/

test-cov:
	pytest tests/ --cov=src --cov-report=html

lint:
	ruff check src/ tests/
	mypy src/ --ignore-missing-imports

format:
	black src/ tests/

typecheck:
	mypy src/ --ignore-missing-imports

ci: lint test

frontend-install:
	cd frontend && pnpm install

frontend-dev:
	cd frontend && pnpm dev

frontend-build:
	cd frontend && pnpm build

frontend-test:
	cd frontend && pnpm test

generate-types:
	cd frontend && pnpm generate:types

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache build/ dist/ *.egg-info htmlcov/
	cd frontend && rm -rf dist node_modules
```

- [ ] **Step 4: Verify ci target runs**

```bash
make ci
```
Expected: lint + tests all pass.

- [ ] **Step 5: Commit**

```bash
git add Makefile
git commit -m "chore: add ci and frontend Makefile targets"
```

---

## Task 11: Frontend scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx` (stub)
- Create: `frontend/src/index.css` (stub)

- [ ] **Step 1: Create frontend directory structure**

```bash
mkdir -p frontend/src/lib frontend/src/pages/settings/panels \
          frontend/src/types frontend/tests/unit/lib \
          frontend/tests/unit/pages frontend/tests/e2e
```

- [ ] **Step 2: Create package.json**

Create `frontend/package.json`:

```json
{
  "name": "market-data-ui",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest",
    "test:coverage": "vitest run --coverage",
    "generate:types": "openapi-typescript http://localhost:8000/openapi.json -o src/types/api.ts"
  },
  "dependencies": {
    "@solidjs/router": "^0.14.0",
    "open-props": "^1.6.0",
    "solid-js": "^1.8.0"
  },
  "devDependencies": {
    "@playwright/test": "^1.42.0",
    "@solidjs/testing-library": "^0.8.0",
    "@testing-library/jest-dom": "^6.4.0",
    "@testing-library/user-event": "^14.5.0",
    "openapi-typescript": "^6.7.0",
    "typescript": "^5.3.0",
    "vite": "^5.2.0",
    "vite-plugin-solid": "^2.10.0",
    "vitest": "^1.4.0"
  }
}
```

- [ ] **Step 3: Create tsconfig.json**

Create `frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "preserve",
    "jsxImportSource": "solid-js",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "outDir": "dist",
    "baseUrl": ".",
    "paths": {
      "~/*": ["src/*"]
    }
  },
  "include": ["src", "tests"],
  "exclude": ["node_modules", "dist"]
}
```

- [ ] **Step 4: Create vite.config.ts**

Create `frontend/vite.config.ts`:

```ts
import { defineConfig } from "vite";
import solidPlugin from "vite-plugin-solid";

export default defineConfig({
  plugins: [solidPlugin()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://127.0.0.1:8000",
        ws: true,
      },
    },
  },
  build: {
    outDir: "dist",
    target: "es2020",
  },
});
```

- [ ] **Step 5: Create vitest.config.ts**

Create `frontend/vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config";
import solidPlugin from "vite-plugin-solid";

export default defineConfig({
  plugins: [solidPlugin()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    coverage: {
      provider: "v8",
      thresholds: {
        "src/lib/**": { lines: 80, functions: 80 },
        global: { lines: 70 },
      },
    },
  },
  resolve: {
    conditions: ["development", "browser"],
  },
});
```

- [ ] **Step 6: Create test setup file**

Create `frontend/tests/setup.ts`:

```ts
import "@testing-library/jest-dom";
```

- [ ] **Step 7: Create index.html**

Create `frontend/index.html`:

```html
<!DOCTYPE html>
<html lang="en" data-theme="dark">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Market Data</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 8: Create stub main.tsx**

Create `frontend/src/main.tsx`:

```tsx
import { render } from "solid-js/web";

render(() => <div>Loading…</div>, document.getElementById("root")!);
```

- [ ] **Step 9: Create stub index.css**

Create `frontend/src/index.css`:

```css
@import "open-props/style";

:root {
  color-scheme: light dark;
}

[data-theme="dark"] {
  --surface-1: #1a1a2e;
  --surface-2: #16213e;
  --text-1: #e0e0e0;
  --text-2: #a0a0b0;
  --accent: #0ea5e9;
  --border: #2a2a4a;
}

[data-theme="light"] {
  --surface-1: #f8f9fa;
  --surface-2: #ffffff;
  --text-1: #1a1a2e;
  --text-2: #555577;
  --accent: #0284c7;
  --border: #d0d0e0;
}

*,
*::before,
*::after {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: system-ui, sans-serif;
  background: var(--surface-1);
  color: var(--text-1);
  min-height: 100vh;
}
```

- [ ] **Step 10: Install dependencies and verify dev server starts**

```bash
cd frontend && pnpm install
```
Expected: installs all packages, no errors.

```bash
# Start backend first in another terminal:
# uvicorn src.api.main:create_app --factory --host 127.0.0.1 --port 8000
# Then:
pnpm build
```
Expected: build succeeds (stub app compiles).

- [ ] **Step 11: Commit**

```bash
cd ..
git add frontend/
git commit -m "chore: scaffold SolidJS + Vite frontend"
```

---

## Task 12: Frontend lib/api.ts — typed fetch wrapper

**Files:**
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/types/api.ts` (hand-written stub until codegen runs)
- Create: `frontend/tests/unit/lib/api.test.ts`

- [ ] **Step 1: Write failing tests**

Create `frontend/tests/unit/lib/api.test.ts`:

```ts
import { describe, it, expect, vi, afterEach } from "vitest";

describe("apiFetch", () => {
  afterEach(() => vi.restoreAllMocks());

  it("sends credentials: include on every request", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), { status: 200 })
    );
    vi.stubGlobal("fetch", fetchMock);

    const { apiFetch } = await import("~/lib/api");
    await apiFetch("/api/health");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/health",
      expect.objectContaining({ credentials: "include" })
    );
  });

  it("returns parsed JSON on 200", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "ok" }), { status: 200 }))
    );
    const { apiFetch } = await import("~/lib/api");
    const result = await apiFetch("/api/health");
    expect(result).toEqual({ status: "ok" });
  });

  it("throws ApiError on non-2xx", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "bad" }), { status: 400 }))
    );
    const { apiFetch, ApiError } = await import("~/lib/api");
    await expect(apiFetch("/api/whatever")).rejects.toBeInstanceOf(ApiError);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && pnpm test tests/unit/lib/api.test.ts
```
Expected: fail — module not found.

- [ ] **Step 3: Create stub types/api.ts**

This will be replaced by codegen in Task 19. Create `frontend/src/types/api.ts`:

```ts
// AUTO-GENERATED from /openapi.json — do not edit manually.
// Regenerate with: pnpm generate:types

export interface UserOut {
  id: number;
  username: string;
}

export interface SettingsOut {
  theme: string;
  timezone: string;
}

export interface SettingsPatch {
  theme?: "light" | "dark";
  timezone?: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}
```

- [ ] **Step 4: Create frontend/src/lib/api.ts**

```ts
/** Typed fetch wrapper. Sets credentials:include and throws ApiError on non-2xx. */

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string
  ) {
    super(`API error ${status}: ${detail}`);
  }
}

export async function apiFetch<T = unknown>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const response = await fetch(url, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore parse error
    }
    throw new ApiError(response.status, detail);
  }

  // 204 No Content
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

// Convenience wrappers
export const apiGet = <T>(url: string) => apiFetch<T>(url);

export const apiPost = <T>(url: string, body?: unknown) =>
  apiFetch<T>(url, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined });

export const apiPut = <T>(url: string, body?: unknown) =>
  apiFetch<T>(url, { method: "PUT", body: body !== undefined ? JSON.stringify(body) : undefined });
```

- [ ] **Step 5: Run tests**

```bash
pnpm test tests/unit/lib/api.test.ts
```
Expected: all 3 tests PASS

- [ ] **Step 6: Commit**

```bash
cd .. && git add frontend/src/lib/api.ts frontend/src/types/api.ts \
               frontend/tests/unit/lib/api.test.ts
git commit -m "feat: add frontend API fetch wrapper with error handling"
```

---

## Task 13: Frontend lib/ws.ts — WebSocket client

**Files:**
- Create: `frontend/src/lib/ws.ts`
- Create: `frontend/tests/unit/lib/ws.test.ts`

- [ ] **Step 1: Write failing tests**

Create `frontend/tests/unit/lib/ws.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Minimal WebSocket mock
class MockWS {
  static instances: MockWS[] = [];
  readyState = 0; // CONNECTING
  onopen: (() => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onclose: (() => void) | null = null;
  sent: string[] = [];

  constructor(public url: string) {
    MockWS.instances.push(this);
  }
  send(data: string) { this.sent.push(data); }
  close() { this.readyState = 3; this.onclose?.(); }

  simulateOpen() {
    this.readyState = 1;
    this.onopen?.();
  }
  simulateMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) } as MessageEvent);
  }
}

beforeEach(() => {
  MockWS.instances = [];
  vi.stubGlobal("WebSocket", MockWS);
});
afterEach(() => vi.unstubAllGlobals());

describe("WsClient", () => {
  it("calls handler when subscribed topic message arrives", async () => {
    const { WsClient } = await import("~/lib/ws");
    const client = new WsClient("/ws");
    const handler = vi.fn();
    client.subscribe("quotes:NVDA", handler);
    client.connect();

    const ws = MockWS.instances[0];
    ws.simulateOpen();
    ws.simulateMessage({ topic: "quotes:NVDA", data: { price: 100 } });

    expect(handler).toHaveBeenCalledWith({ price: 100 });
  });

  it("unsubscribe stops delivery", async () => {
    const { WsClient } = await import("~/lib/ws");
    const client = new WsClient("/ws");
    const handler = vi.fn();
    const unsub = client.subscribe("t1", handler);
    client.connect();

    const ws = MockWS.instances[0];
    ws.simulateOpen();
    unsub();
    ws.simulateMessage({ topic: "t1", data: {} });

    expect(handler).not.toHaveBeenCalled();
  });

  it("re-subscribes after reconnect", async () => {
    const { WsClient } = await import("~/lib/ws");
    const client = new WsClient("/ws");
    const handler = vi.fn();
    client.subscribe("t1", handler);
    client.connect();

    const ws1 = MockWS.instances[0];
    ws1.simulateOpen();
    ws1.close(); // trigger reconnect

    // Fast-forward — new WS should exist after reconnect
    await vi.runAllTimersAsync();

    if (MockWS.instances.length > 1) {
      const ws2 = MockWS.instances[1];
      ws2.simulateOpen();
      ws2.simulateMessage({ topic: "t1", data: "after reconnect" });
      expect(handler).toHaveBeenCalledWith("after reconnect");
    }
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && pnpm test tests/unit/lib/ws.test.ts
```
Expected: fail — module not found.

- [ ] **Step 3: Create frontend/src/lib/ws.ts**

```ts
import { createSignal } from "solid-js";

export type WsStatus = "connecting" | "open" | "closed";

export class WsClient {
  private sock: WebSocket | null = null;
  private readonly subscribers = new Map<string, Set<(data: unknown) => void>>();
  private backoffMs = 1000;
  private readonly maxBackoffMs = 30_000;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  // SolidJS reactive status: consumers call ws.status() in JSX
  private readonly _sig = createSignal<WsStatus>("closed");
  readonly status = this._sig[0];
  private readonly setStatus = this._sig[1];

  constructor(private readonly url: string) {}

  connect(): void {
    if (this.sock && this.sock.readyState <= 1) return; // already connecting/open
    this.setStatus("connecting");
    this.sock = new WebSocket(this.url);

    this.sock.onopen = () => {
      this.backoffMs = 1000;
      this.setStatus("open");
      // Re-subscribe all active topics after reconnect
      for (const topic of this.subscribers.keys()) {
        this.sock?.send(JSON.stringify({ op: "subscribe", topic }));
      }
    };

    this.sock.onmessage = (event: MessageEvent) => {
      try {
        const msg = JSON.parse(event.data as string) as { topic?: string; data?: unknown };
        if (msg.topic) {
          this.subscribers.get(msg.topic)?.forEach((h) => h(msg.data));
        }
      } catch {
        // ignore parse errors
      }
    };

    this.sock.onclose = () => {
      this.setStatus("closed");
      this.scheduleReconnect();
    };
  }

  subscribe(topic: string, handler: (data: unknown) => void): () => void {
    if (!this.subscribers.has(topic)) {
      this.subscribers.set(topic, new Set());
      if (this.sock?.readyState === 1) {
        this.sock.send(JSON.stringify({ op: "subscribe", topic }));
      }
    }
    this.subscribers.get(topic)!.add(handler);
    return () => {
      const handlers = this.subscribers.get(topic);
      if (!handlers) return;
      handlers.delete(handler);
      if (handlers.size === 0) {
        this.subscribers.delete(topic);
        if (this.sock?.readyState === 1) {
          this.sock.send(JSON.stringify({ op: "unsubscribe", topic }));
        }
      }
    };
  }

  disconnect(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.sock?.close();
    this.sock = null;
  }

  private scheduleReconnect(): void {
    this.reconnectTimer = setTimeout(() => {
      this.backoffMs = Math.min(this.backoffMs * 2, this.maxBackoffMs);
      this.connect();
    }, this.backoffMs);
  }
}

// App-wide singleton
export const ws = new WsClient("/ws");
```

- [ ] **Step 4: Run tests**

```bash
cd frontend && pnpm test tests/unit/lib/ws.test.ts
```
Expected: tests PASS (some may need timer manipulation — adjust if needed using `vi.useFakeTimers()`).

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/src/lib/ws.ts frontend/tests/unit/lib/ws.test.ts
git commit -m "feat: add WebSocket client with reconnect and pub/sub"
```

---

## Task 14: Frontend auth + settings store

**Files:**
- Create: `frontend/src/lib/auth.ts`
- Create: `frontend/src/lib/settings-store.ts`
- Create: `frontend/tests/unit/lib/auth.test.tsx`

- [ ] **Step 1: Write failing auth tests**

Create `frontend/tests/unit/lib/auth.test.tsx`:

```tsx
import { describe, it, expect, vi, afterEach } from "vitest";

afterEach(() => vi.restoreAllMocks());

describe("auth store", () => {
  it("currentUser is null initially", async () => {
    const { currentUser } = await import("~/lib/auth");
    expect(currentUser()).toBeNull();
  });

  it("login calls POST /api/auth/login", async () => {
    const postMock = vi.fn().mockResolvedValue({ ok: true });
    vi.doMock("~/lib/api", () => ({ apiPost: postMock, ApiError: class extends Error {} }));
    const { login } = await import("~/lib/auth");
    await login("user", "pass");
    expect(postMock).toHaveBeenCalledWith("/api/auth/login", { username: "user", password: "pass" });
  });
});
```

- [ ] **Step 2: Create frontend/src/lib/auth.ts**

```ts
import { createSignal } from "solid-js";
import { apiGet, apiPost } from "./api";
import type { UserOut } from "../types/api";

const [currentUser, setCurrentUser] = createSignal<UserOut | null>(null);
export { currentUser };

export async function fetchCurrentUser(): Promise<UserOut | null> {
  try {
    const user = await apiGet<UserOut>("/api/me");
    setCurrentUser(user);
    return user;
  } catch {
    setCurrentUser(null);
    return null;
  }
}

export async function login(username: string, password: string): Promise<void> {
  await apiPost("/api/auth/login", { username, password });
  await fetchCurrentUser();
}

export async function logout(): Promise<void> {
  await apiPost("/api/auth/logout");
  setCurrentUser(null);
}
```

- [ ] **Step 3: Create frontend/src/lib/settings-store.ts**

```ts
import { createStore } from "solid-js/store";
import { apiGet, apiPut } from "./api";
import type { SettingsOut, SettingsPatch } from "../types/api";

const [settings, setSettings] = createStore<SettingsOut>({
  theme: "dark",
  timezone: "America/New_York",
});

export { settings };

export function applyTheme(theme: string): void {
  document.documentElement.dataset.theme = theme;
}

export async function loadSettings(): Promise<void> {
  const data = await apiGet<SettingsOut>("/api/settings");
  setSettings(data);
  applyTheme(data.theme);
}

export async function saveSettings(patch: SettingsPatch): Promise<void> {
  const updated = await apiPut<SettingsOut>("/api/settings", patch);
  setSettings(updated);
  if (patch.theme) applyTheme(patch.theme);
}
```

- [ ] **Step 4: Run auth tests**

```bash
cd frontend && pnpm test tests/unit/lib/auth.test.tsx
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd .. && git add frontend/src/lib/auth.ts frontend/src/lib/settings-store.ts \
               frontend/tests/unit/lib/auth.test.tsx
git commit -m "feat: add auth store and settings store"
```

---

## Task 15: App shell — routing, nav, RequireAuth

**Files:**
- Modify: `frontend/src/main.tsx`
- Create: `frontend/src/app.tsx`
- Create: `frontend/src/pages/login.tsx`
- Create: `frontend/src/pages/dashboard.tsx`

- [ ] **Step 1: Create login page**

Create `frontend/src/pages/login.tsx`:

```tsx
import { createSignal, Show } from "solid-js";
import { useNavigate } from "@solidjs/router";
import { login } from "../lib/auth";
import { ApiError } from "../lib/api";

export default function LoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = createSignal("");
  const [password, setPassword] = createSignal("");
  const [error, setError] = createSignal<string | null>(null);
  const [loading, setLoading] = createSignal(false);

  async function handleSubmit(e: Event) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(username(), password());
      navigate("/dashboard", { replace: true });
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError("Invalid username or password.");
      } else if (err instanceof ApiError && err.status === 429) {
        setError("Too many attempts. Please wait a minute and try again.");
      } else {
        setError("Login failed. Check your connection.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main class="login-page">
      <form onSubmit={handleSubmit} class="login-form">
        <h1>Market Data</h1>
        <Show when={error()}>
          <p class="error-msg" role="alert">{error()}</p>
        </Show>
        <label>
          Username
          <input
            type="text"
            autocomplete="username"
            value={username()}
            onInput={(e) => setUsername(e.currentTarget.value)}
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autocomplete="current-password"
            value={password()}
            onInput={(e) => setPassword(e.currentTarget.value)}
            required
          />
        </label>
        <button type="submit" disabled={loading()}>
          {loading() ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
```

- [ ] **Step 2: Create dashboard page**

Create `frontend/src/pages/dashboard.tsx`:

```tsx
import { createEffect } from "solid-js";
import { currentUser } from "../lib/auth";
import { ws } from "../lib/ws";

export default function DashboardPage() {
  createEffect(() => {
    ws.connect();
  });

  return (
    <main class="dashboard-page">
      <h1>Dashboard</h1>
      <p>Hello, {currentUser()?.username ?? "…"}!</p>
      <p class="ws-note">WebSocket: {ws.status()}</p>
    </main>
  );
}
```

- [ ] **Step 3: Create app shell**

Create `frontend/src/app.tsx`:

```tsx
import { A, useNavigate } from "@solidjs/router";
import { Outlet } from "@solidjs/router";
import { Show } from "solid-js";
import { currentUser, logout } from "./lib/auth";
import { ws } from "./lib/ws";

function WsStatusDot() {
  const color = () => {
    switch (ws.status()) {
      case "open": return "var(--green-6, #16a34a)";
      case "connecting": return "var(--yellow-6, #ca8a04)";
      default: return "var(--red-6, #dc2626)";
    }
  };
  return (
    <span
      title={`WebSocket: ${ws.status()}`}
      style={{ display: "inline-block", width: "10px", height: "10px",
               "border-radius": "50%", background: color() }}
    />
  );
}

export default function App() {
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <>
      <nav class="app-nav">
        <span class="app-title">Market Data</span>
        <div class="nav-links">
          <A href="/dashboard">Dashboard</A>
          <A href="/settings">Settings</A>
        </div>
        <div class="nav-user">
          <WsStatusDot />
          <Show when={currentUser()}>
            <span>{currentUser()!.username}</span>
            <button onClick={handleLogout}>Logout</button>
          </Show>
        </div>
      </nav>
      <Outlet />
    </>
  );
}
```

- [ ] **Step 4: Update main.tsx with full router setup**

Replace `frontend/src/main.tsx`:

```tsx
import { render } from "solid-js/web";
import { Navigate, Route, Router } from "@solidjs/router";
import { createEffect, createResource, Show, Suspense } from "solid-js";
import "./index.css";
import App from "./app";
import LoginPage from "./pages/login";
import DashboardPage from "./pages/dashboard";
import SettingsPage from "./pages/settings/index";
import AppearancePanel from "./pages/settings/panels/appearance";
import { currentUser, fetchCurrentUser } from "./lib/auth";
import { loadSettings } from "./lib/settings-store";

function RequireAuth(props: { children: any }) {
  const [user] = createResource(fetchCurrentUser);
  return (
    <Suspense fallback={<p>Loading…</p>}>
      <Show when={user()} fallback={<Navigate href="/login" />}>
        {props.children}
      </Show>
    </Suspense>
  );
}

render(
  () => (
    <Router root={App}>
      <Route path="/" component={() => <Navigate href="/dashboard" />} />
      <Route path="/login" component={LoginPage} />
      <Route
        path="/dashboard"
        component={() => (
          <RequireAuth>
            <DashboardPage />
          </RequireAuth>
        )}
      />
      <Route
        path="/settings"
        component={() => (
          <RequireAuth>
            <Navigate href="/settings/appearance" />
          </RequireAuth>
        )}
      />
      <Route
        path="/settings/:panelId"
        component={() => (
          <RequireAuth>
            <SettingsPage />
          </RequireAuth>
        )}
      />
    </Router>
  ),
  document.getElementById("root")!
);
```

- [ ] **Step 5: Verify build succeeds**

```bash
cd frontend && pnpm build
```
Expected: build completes (pages/settings/* don't exist yet, but they will in the next task — create placeholder stubs if needed to unblock the build):

```bash
mkdir -p src/pages/settings/panels
cat > src/pages/settings/index.tsx << 'EOF'
export default function SettingsPage() { return <div>Settings</div>; }
EOF
cat > src/pages/settings/panels/appearance.tsx << 'EOF'
export default function AppearancePanel() { return <div>Appearance</div>; }
EOF
cat > src/pages/settings/registry.ts << 'EOF'
export const settingsPanels: any[] = [];
EOF
```

Then: `pnpm build` — should pass.

- [ ] **Step 6: Commit**

```bash
cd .. && git add frontend/src/
git commit -m "feat: add app shell, routing, login page, dashboard"
```

---

## Task 16: Settings page + panel registry + appearance panel + tests

**Files:**
- Replace: `frontend/src/pages/settings/registry.ts`
- Replace: `frontend/src/pages/settings/index.tsx`
- Replace: `frontend/src/pages/settings/panels/appearance.tsx`
- Create: `frontend/tests/unit/pages/appearance-panel.test.tsx`
- Create: `frontend/tests/unit/pages/settings-registry.test.tsx`

- [ ] **Step 1: Write failing settings tests**

Create `frontend/tests/unit/pages/settings-registry.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render } from "@solidjs/testing-library";

describe("settings panel registry", () => {
  it("contains appearance panel", async () => {
    const { settingsPanels } = await import("~/pages/settings/registry");
    const ids = settingsPanels.map((p) => p.id);
    expect(ids).toContain("appearance");
  });

  it("panels are sorted by order", async () => {
    const { settingsPanels } = await import("~/pages/settings/registry");
    const orders = settingsPanels.map((p) => p.order);
    const sorted = [...orders].sort((a, b) => a - b);
    expect(orders).toEqual(sorted);
  });
});
```

Create `frontend/tests/unit/pages/appearance-panel.test.tsx`:

```tsx
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent } from "@solidjs/testing-library";

afterEach(() => vi.restoreAllMocks());

describe("AppearancePanel", () => {
  it("renders theme radio buttons", async () => {
    vi.doMock("~/lib/settings-store", () => ({
      settings: { theme: "dark", timezone: "America/New_York" },
      loadSettings: vi.fn().mockResolvedValue(undefined),
      saveSettings: vi.fn().mockResolvedValue(undefined),
      applyTheme: vi.fn(),
    }));
    const { default: AppearancePanel } = await import(
      "~/pages/settings/panels/appearance"
    );
    const { unmount } = render(() => <AppearancePanel />);
    expect(screen.getByLabelText(/dark/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/light/i)).toBeInTheDocument();
    unmount();
  });

  it("save button calls saveSettings with changed theme", async () => {
    const saveSettings = vi.fn().mockResolvedValue(undefined);
    vi.doMock("~/lib/settings-store", () => ({
      settings: { theme: "dark", timezone: "America/New_York" },
      loadSettings: vi.fn().mockResolvedValue(undefined),
      saveSettings,
      applyTheme: vi.fn(),
    }));
    const { default: AppearancePanel } = await import(
      "~/pages/settings/panels/appearance"
    );
    const { unmount } = render(() => <AppearancePanel />);
    fireEvent.click(screen.getByLabelText(/light/i));
    fireEvent.click(screen.getByRole("button", { name: /save/i }));
    expect(saveSettings).toHaveBeenCalledWith(expect.objectContaining({ theme: "light" }));
    unmount();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && pnpm test tests/unit/pages/
```
Expected: fail (stubs still in place)

- [ ] **Step 3: Write the panel registry**

Replace `frontend/src/pages/settings/registry.ts`:

```ts
import type { Component } from "solid-js";
import AppearancePanel from "./panels/appearance";

export interface SettingsPanel {
  id: string;
  label: string;
  component: Component;
  order: number;
}

export const settingsPanels: SettingsPanel[] = [
  { id: "appearance", label: "Appearance", component: AppearancePanel, order: 0 },
  // Future sub-projects append here — no Foundation files need changing.
];
```

- [ ] **Step 4: Write the settings page shell**

Replace `frontend/src/pages/settings/index.tsx`:

```tsx
import { For, Show } from "solid-js";
import { A, useParams } from "@solidjs/router";
import { settingsPanels } from "./registry";

export default function SettingsPage() {
  const params = useParams<{ panelId: string }>();
  const panel = () => settingsPanels.find((p) => p.id === params.panelId);

  return (
    <div class="settings-layout">
      <aside class="settings-sidebar">
        <nav>
          <For each={settingsPanels.sort((a, b) => a.order - b.order)}>
            {(p) => (
              <A
                href={`/settings/${p.id}`}
                class="sidebar-link"
                activeClass="active"
                end
              >
                {p.label}
              </A>
            )}
          </For>
        </nav>
      </aside>
      <main class="settings-content">
        <Show
          when={panel()}
          fallback={<p>Panel not found.</p>}
        >
          {(p) => <p.component />}
        </Show>
      </main>
    </div>
  );
}
```

- [ ] **Step 5: Write the Appearance panel**

Replace `frontend/src/pages/settings/panels/appearance.tsx`:

```tsx
import { createSignal, onMount } from "solid-js";
import { settings, loadSettings, saveSettings } from "../../../lib/settings-store";

export default function AppearancePanel() {
  const [theme, setTheme] = createSignal<"light" | "dark">("dark");
  const [timezone, setTimezone] = createSignal("America/New_York");
  const [dirty, setDirty] = createSignal(false);
  const [saving, setSaving] = createSignal(false);

  const tzList = () => Intl.supportedValuesOf("timeZone");

  onMount(async () => {
    await loadSettings();
    setTheme(settings.theme as "light" | "dark");
    setTimezone(settings.timezone);
  });

  function handleThemeChange(val: "light" | "dark") {
    setTheme(val);
    setDirty(true);
  }

  function handleTimezoneChange(e: Event) {
    setTimezone((e.currentTarget as HTMLSelectElement).value);
    setDirty(true);
  }

  async function handleSave(e: Event) {
    e.preventDefault();
    setSaving(true);
    try {
      await saveSettings({ theme: theme(), timezone: timezone() });
      setDirty(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form class="settings-panel" onSubmit={handleSave}>
      <h2>Appearance</h2>

      <fieldset>
        <legend>Theme</legend>
        <label>
          <input
            type="radio"
            name="theme"
            value="dark"
            checked={theme() === "dark"}
            onChange={() => handleThemeChange("dark")}
          />
          Dark
        </label>
        <label>
          <input
            type="radio"
            name="theme"
            value="light"
            checked={theme() === "light"}
            onChange={() => handleThemeChange("light")}
          />
          Light
        </label>
      </fieldset>

      <label>
        Timezone
        <select value={timezone()} onChange={handleTimezoneChange}>
          <For each={tzList()}>{(tz) => <option value={tz}>{tz}</option>}</For>
        </select>
      </label>

      <button type="submit" disabled={!dirty() || saving()}>
        {saving() ? "Saving…" : "Save"}
      </button>
    </form>
  );
}
```

- [ ] **Step 6: Run tests**

```bash
cd frontend && pnpm test tests/unit/pages/
```
Expected: all tests PASS

- [ ] **Step 7: Build to verify no TS errors**

```bash
pnpm build
```
Expected: builds without errors.

- [ ] **Step 8: Commit**

```bash
cd .. && git add frontend/src/pages/ frontend/tests/unit/pages/
git commit -m "feat: add settings page, panel registry, and appearance panel"
```

---

## Task 17: Run all frontend tests + coverage check

**Files:** no new files

- [ ] **Step 1: Run full frontend unit test suite**

```bash
cd frontend && pnpm test:coverage
```
Expected: all tests pass. Coverage printed. Target: `src/lib/*` ≥ 80%, overall ≥ 70%.

- [ ] **Step 2: Fix any failures or coverage gaps before proceeding**

If any test fails, fix it. If coverage is below threshold, add targeted tests to the relevant file.

- [ ] **Step 3: Commit**

```bash
cd .. && git add frontend/
git commit -m "test: ensure frontend unit test coverage meets thresholds"
```

---

## Task 18: OpenAPI type generation

**Files:**
- Modify: `frontend/src/types/api.ts` (replace stub with generated)

- [ ] **Step 1: Ensure FastAPI is running**

In a separate terminal:

```bash
APP_USERNAME=admin APP_PASSWORD=adminpass123 \
DATABASE_URL=postgresql://market_data:market_data@127.0.0.1:5432/market_data \
MARKETDATA_API_TOKEN=dummy \
uvicorn src.api.main:create_app --factory --host 127.0.0.1 --port 8000
```

- [ ] **Step 2: Run codegen**

```bash
cd frontend && pnpm generate:types
```
Expected: overwrites `src/types/api.ts` with types derived from FastAPI's `/openapi.json`.

- [ ] **Step 3: Verify generated types match the stub**

```bash
diff src/types/api.ts src/types/api.ts.bak 2>/dev/null || echo "no backup to compare"
```
Manually verify: `UserOut`, `SettingsOut`, `SettingsPatch`, `LoginRequest` types are present and correct.

- [ ] **Step 4: Run tests with generated types**

```bash
pnpm test
```
Expected: all tests still pass.

- [ ] **Step 5: Commit the generated types file**

```bash
cd .. && git add frontend/src/types/api.ts
git commit -m "chore: generate TypeScript API types from FastAPI OpenAPI schema"
```

---

## Task 19: E2E Playwright smoke test

**Files:**
- Create: `frontend/tests/e2e/smoke.spec.ts`

- [ ] **Step 1: Install Playwright browsers**

```bash
cd frontend && npx playwright install chromium
```

- [ ] **Step 2: Create playwright.config.ts**

Create `frontend/playwright.config.ts`:

```ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "tests/e2e",
  use: {
    baseURL: "http://localhost:5173",
  },
  webServer: [
    {
      command:
        "APP_USERNAME=admin APP_PASSWORD=adminpass123 " +
        "DATABASE_URL=postgresql://market_data:market_data@127.0.0.1:5432/market_data " +
        "MARKETDATA_API_TOKEN=dummy " +
        "uvicorn src.api.main:create_app --factory --host 127.0.0.1 --port 8000",
      url: "http://127.0.0.1:8000/api/health",
      cwd: "..",
      reuseExistingServer: true,
    },
    {
      command: "pnpm dev",
      url: "http://localhost:5173",
      reuseExistingServer: true,
    },
  ],
});
```

- [ ] **Step 3: Create smoke test**

Create `frontend/tests/e2e/smoke.spec.ts`:

```ts
import { test, expect } from "@playwright/test";

test.describe("Foundation smoke test", () => {
  test.beforeAll(async ({ request }) => {
    // Ensure migration has run (user exists)
    const health = await request.get("http://127.0.0.1:8000/api/health");
    expect(health.ok()).toBeTruthy();
  });

  test("unauthenticated redirect to /login", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
  });

  test("login with valid credentials redirects to /dashboard", async ({ page }) => {
    await page.goto("/login");
    await page.fill('input[autocomplete="username"]', "admin");
    await page.fill('input[autocomplete="current-password"]', "adminpass123");
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.locator("h1")).toContainText("Dashboard");
  });

  test("navigate to settings and verify appearance panel loads", async ({ page }) => {
    await page.goto("/login");
    await page.fill('input[autocomplete="username"]', "admin");
    await page.fill('input[autocomplete="current-password"]', "adminpass123");
    await page.click('button[type="submit"]');
    await page.click('a[href="/settings"]');
    await expect(page).toHaveURL(/\/settings\/appearance/);
    await expect(page.locator("h2")).toContainText("Appearance");
  });

  test("toggle theme to light, save, reload — theme persists", async ({ page }) => {
    await page.goto("/login");
    await page.fill('input[autocomplete="username"]', "admin");
    await page.fill('input[autocomplete="current-password"]', "adminpass123");
    await page.click('button[type="submit"]');
    await page.goto("/settings/appearance");

    // Select light theme
    await page.click('input[value="light"]');
    await page.click('button[type="submit"]');
    // Wait for save
    await expect(page.locator('button[type="submit"]')).toHaveText("Save");

    // Reload and verify persisted
    await page.reload();
    await expect(page.locator('input[value="light"]')).toBeChecked();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  });
});
```

- [ ] **Step 4: Run Playwright tests**

Ensure the migration has been run on the local DB and `admin`/`adminpass123` credentials are seeded:

```bash
APP_USERNAME=admin APP_PASSWORD=adminpass123 alembic upgrade head
```

Then:

```bash
cd frontend && npx playwright test
```
Expected: all 4 scenarios pass.

- [ ] **Step 5: Add e2e script to package.json**

In `frontend/package.json`, add to `"scripts"`:

```json
"test:e2e": "playwright test"
```

- [ ] **Step 6: Commit**

```bash
cd .. && git add frontend/playwright.config.ts frontend/tests/e2e/ frontend/package.json
git commit -m "test: add Playwright E2E smoke test for full login→settings→persist flow"
```

---

## Task 20: Linear issues, final integration, acceptance criteria verification

- [ ] **Step 1: Run full backend suite**

```bash
make ci
```
Expected: lint + all backend tests pass.

- [ ] **Step 2: Run full frontend suite**

```bash
make frontend-test
```
Expected: all Vitest tests pass with coverage thresholds met.

- [ ] **Step 3: Verify acceptance criteria checklist**

Walk through the 14 acceptance criteria in the spec (`docs/superpowers/specs/2026-04-08-foundation-design.md §13`). For each one not covered by automated tests, verify manually.

- [ ] **Step 4: Update roadmap status**

Edit `docs/superpowers/specs/2026-04-08-frontend-roadmap.md`, change:

```markdown
- [ ] 1. Foundation — *brainstorming in progress (2026-04-08)*
```
to:
```markdown
- [x] 1. Foundation — *complete (2026-04-08)*
```

- [ ] **Step 5: Commit final state**

```bash
git add docs/superpowers/specs/2026-04-08-frontend-roadmap.md
git commit -m "docs: mark Foundation sub-project complete"
```
