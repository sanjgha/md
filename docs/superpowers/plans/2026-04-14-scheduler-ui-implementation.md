# Scheduler UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/schedule` page that lets users view and control the EOD and pre-close scanner jobs — including time edits, enable/disable, on-demand runs, auto-save to watchlist, and a 7-day run history.

**Architecture:** A `BackgroundScheduler` starts inside the FastAPI `lifespan` alongside the API server. Its configuration is persisted in a new `schedule_config` DB table so time edits survive restarts. Three new API routes (`GET`, `PATCH`, `POST /run`) expose job state and control to the frontend. The SolidJS frontend adds a `/schedule` route with two job cards and a history table.

**Tech Stack:** Python · SQLAlchemy · Alembic · APScheduler (`apscheduler>=3`) · FastAPI · SolidJS · TypeScript

---

## File Map

**Created:**
- `src/api/schedule/__init__.py`
- `src/api/schedule/jobs.py` — EOD and pre-close job callbacks
- `src/api/schedule/manager.py` — `ScheduleManager` class (BackgroundScheduler wrapper)
- `src/api/schedule/schemas.py` — Pydantic request/response models
- `src/api/schedule/routes.py` — FastAPI router (`/api/schedule/jobs`)
- `tests/unit/api/test_schedule_manager.py` — unit tests for ScheduleManager
- `tests/integration/api/test_schedule.py` — integration tests for API routes
- `frontend/src/pages/schedule/types.ts` — TypeScript types
- `frontend/src/lib/schedule-api.ts` — API client
- `frontend/src/pages/schedule/job-card.tsx` — job card component
- `frontend/src/pages/schedule/index.tsx` — schedule page

**Modified:**
- `src/db/models.py` — add `ScheduleConfig` model
- `src/db/migrations/versions/<hash>_add_schedule_config.py` — Alembic migration
- `src/api/main.py` — wire `ScheduleManager` into lifespan + include router
- `frontend/src/main.tsx` — add `/schedule` route
- `frontend/src/app.tsx` — add Schedule nav link

---

## Task 0: Create Linear Issues

Create one Linear issue per task below before writing any code. Use the template at `docs/linear/templates/new-issue.md`. Label each with the project's current cycle.

Issues to create (9 total):

| # | Title | Acceptance Criteria Summary |
|---|---|---|
| A | Add `schedule_config` DB model and Alembic migration | Table exists, seeds two rows, `alembic upgrade head` passes |
| B | Implement EOD and pre-close job callbacks | `run_eod_job(db)` and `run_pre_close_job(db)` return result count; unit tested |
| C | Implement `ScheduleManager` | `start`, `stop`, `reschedule`, `pause`, `resume`, `run_now`; unit tested |
| D | Add `/api/schedule` Pydantic schemas | `JobResponse`, `JobPatch`, `RunResponse` validated; unit tested |
| E | Add `/api/schedule/jobs` API routes | GET/PATCH/POST routes; auth-gated; integration tested |
| F | Wire scheduler into FastAPI lifespan | Scheduler starts on app boot; router mounted at `/api/schedule` |
| G | Frontend types + API client | `types.ts` + `schedule-api.ts`; mirrors backend schemas |
| H | Frontend `JobCard` component | Inline time edit, toggles, Run Now with spinner; renders correctly |
| I | Frontend `/schedule` page + route wiring | Page loads, shows cards + history, nav link works |

- [ ] **Step 1:** Open Linear and create all 9 issues using the template.
- [ ] **Step 2:** Note each issue ID (e.g. LIN-87 through LIN-95) and add a comment to each linking to `docs/superpowers/specs/2026-04-14-scheduler-ui-design.md`.
- [ ] **Step 3:** Create a new git branch for this feature:

```bash
git checkout -b feature/scheduler-ui-lin87-95
```

---

## Task 1: `ScheduleConfig` DB Model + Migration

**Files:**
- Modify: `src/db/models.py`
- Create: `src/db/migrations/versions/<hash>_add_schedule_config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_db_models.py` already exists — add a test at the bottom:

```python
def test_schedule_config_model_has_expected_columns():
    """ScheduleConfig model defines all required columns."""
    from src.db.models import ScheduleConfig
    from sqlalchemy import inspect

    mapper = inspect(ScheduleConfig)
    col_names = {c.key for c in mapper.columns}
    assert col_names == {"job_id", "hour", "minute", "enabled", "auto_save", "updated_at"}
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/unit/test_db_models.py::test_schedule_config_model_has_expected_columns -v
```
Expected: `ImportError: cannot import name 'ScheduleConfig'`

- [ ] **Step 3: Add `ScheduleConfig` to `src/db/models.py`**

Add after the `ScannerResult` class (around line 248):

```python
class ScheduleConfig(Base):
    """Persists scheduler job configuration across restarts."""

    __tablename__ = "schedule_config"

    job_id = Column(Text, primary_key=True)       # "eod_scan" | "pre_close_scan"
    hour = Column(Integer, nullable=False)
    minute = Column(Integer, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    auto_save = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
```

- [ ] **Step 4: Run test to confirm pass**

```bash
pytest tests/unit/test_db_models.py::test_schedule_config_model_has_expected_columns -v
```
Expected: `PASSED`

- [ ] **Step 5: Generate Alembic migration**

```bash
alembic revision --autogenerate -m "add_schedule_config"
```

Open the generated file in `src/db/migrations/versions/`. Verify it contains a `create_table("schedule_config", ...)` call with all six columns. Then add seed rows to the `upgrade()` function:

```python
def upgrade() -> None:
    op.create_table(
        "schedule_config",
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("hour", sa.Integer(), nullable=False),
        sa.Column("minute", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("auto_save", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.execute(
        """
        INSERT INTO schedule_config (job_id, hour, minute, enabled, auto_save, updated_at)
        VALUES
            ('eod_scan',       16, 15, true, false, now()),
            ('pre_close_scan', 15, 45, true, false, now())
        ON CONFLICT (job_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("schedule_config")
```

- [ ] **Step 6: Apply migration**

```bash
alembic upgrade head
```
Expected: no errors, migration applies cleanly.

- [ ] **Step 7: Commit**

```bash
git add src/db/models.py src/db/migrations/versions/ tests/unit/test_db_models.py
git commit -m "feat: add ScheduleConfig model and migration (LIN-87)"
```

---

## Task 2: Job Callbacks

**Files:**
- Create: `src/api/schedule/__init__.py`
- Create: `src/api/schedule/jobs.py`
- Create: `tests/unit/api/test_schedule_jobs.py`

- [ ] **Step 1: Create the package**

```bash
touch src/api/schedule/__init__.py
```

- [ ] **Step 2: Write the failing tests**

Create `tests/unit/api/test_schedule_jobs.py`:

```python
"""Unit tests for schedule job callbacks."""

from unittest.mock import MagicMock, patch


def test_run_eod_job_returns_result_count():
    """run_eod_job returns the number of matched scanner results."""
    mock_db = MagicMock()

    # Mock Stock query to return empty list (no candles = no results)
    mock_db.query.return_value.options.return_value.all.return_value = []

    from src.api.schedule.jobs import run_eod_job

    count = run_eod_job(mock_db)
    assert count == 0


def test_run_pre_close_job_returns_result_count():
    """run_pre_close_job returns the number of matched pre-close results."""
    mock_db = MagicMock()

    with patch("src.api.schedule.jobs.PreCloseExecutor") as MockExecutor:
        MockExecutor.return_value.run.return_value = [MagicMock(), MagicMock()]
        from src.api.schedule.jobs import run_pre_close_job

        count = run_pre_close_job(mock_db)

    assert count == 2
```

- [ ] **Step 3: Run to confirm failure**

```bash
pytest tests/unit/api/test_schedule_jobs.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.api.schedule.jobs'`

- [ ] **Step 4: Implement `src/api/schedule/jobs.py`**

```python
"""Job callbacks for scheduled scanner runs.

Each function accepts a SQLAlchemy Session and returns the number of matched results.
These are called both by the BackgroundScheduler and by POST /run (synchronously).
"""

import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _build_indicator_registry() -> dict:
    from src.scanner.indicators.moving_averages import SMA, EMA, WMA
    from src.scanner.indicators.momentum import RSI, MACD
    from src.scanner.indicators.volatility import BollingerBands, ATR
    from src.scanner.indicators.support_resistance import SupportResistance
    from src.scanner.indicators.patterns.breakouts import BreakoutDetector

    return {
        "sma": SMA(),
        "ema": EMA(),
        "wma": WMA(),
        "rsi": RSI(),
        "macd": MACD(),
        "bollinger": BollingerBands(),
        "atr": ATR(),
        "support_resistance": SupportResistance(),
        "breakout": BreakoutDetector(),
    }


def _build_scanner_registry():
    from src.scanner.registry import ScannerRegistry
    from src.scanner.scanners import PriceActionScanner, MomentumScanner, VolumeScanner

    registry = ScannerRegistry()
    registry.register("price_action", PriceActionScanner())
    registry.register("momentum", MomentumScanner())
    registry.register("volume", VolumeScanner())
    return registry


def _build_output_handler():
    from src.output.logger import LogFileOutputHandler
    from src.output.composite import CompositeOutputHandler
    from src.config import get_config

    cfg = get_config()
    return CompositeOutputHandler(
        [LogFileOutputHandler(log_file=cfg.LOG_FILE, log_level=cfg.LOG_LEVEL)]
    )


def run_eod_job(db: Session) -> int:
    """Run EOD scan against daily candles. Returns count of matched results."""
    from src.scanner.executor import ScannerExecutor
    from src.db.models import Stock
    from sqlalchemy.orm import joinedload

    indicators = _build_indicator_registry()
    registry = _build_scanner_registry()
    output = _build_output_handler()

    stocks = db.query(Stock).options(joinedload(Stock.daily_candles)).all()
    executor = ScannerExecutor(
        registry=registry,
        indicators_registry=indicators,
        output_handler=output,
        db=db,
    )
    stocks_with_candles = {
        s.id: (
            s.symbol,
            executor._to_candles(sorted(s.daily_candles, key=lambda c: c.timestamp)),
        )
        for s in stocks
        if s.daily_candles
    }
    results = executor.run_eod(stocks_with_candles)
    logger.info("EOD job complete: %d results", len(results))
    return len(results)


def run_pre_close_job(db: Session) -> int:
    """Run pre-close scan using realtime quotes. Returns count of matched results."""
    from src.scanner.pre_close_executor import PreCloseExecutor

    indicators = _build_indicator_registry()
    registry = _build_scanner_registry()
    output = _build_output_handler()

    executor = PreCloseExecutor(
        registry=registry,
        indicators_registry=indicators,
        output_handler=output,
        db=db,
    )
    results = executor.run()
    logger.info("Pre-close job complete: %d results", len(results))
    return len(results)
```

- [ ] **Step 5: Run tests to confirm pass**

```bash
pytest tests/unit/api/test_schedule_jobs.py -v
```
Expected: `2 passed`

- [ ] **Step 6: Commit**

```bash
git add src/api/schedule/ tests/unit/api/test_schedule_jobs.py
git commit -m "feat: add EOD and pre-close job callbacks (LIN-88)"
```

---

## Task 3: `ScheduleManager`

**Files:**
- Create: `src/api/schedule/manager.py`
- Create: `tests/unit/api/test_schedule_manager.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/api/test_schedule_manager.py`:

```python
"""Unit tests for ScheduleManager."""

import threading
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


def _make_manager():
    from src.api.schedule.manager import ScheduleManager
    return ScheduleManager()


def test_run_now_calls_callback_and_returns_count():
    """run_now executes the job callback and returns result_count."""
    manager = _make_manager()
    mock_db = MagicMock()

    # Manually register a fake callback
    manager._callbacks["eod_scan"] = lambda db: 42
    manager._locks["eod_scan"] = threading.Lock()

    count = manager.run_now("eod_scan", mock_db)
    assert count == 42


def test_run_now_raises_when_already_running():
    """run_now raises AlreadyRunningError when the lock is held."""
    from src.api.schedule.manager import AlreadyRunningError

    manager = _make_manager()
    lock = threading.Lock()
    lock.acquire()  # simulate a running job

    manager._callbacks["eod_scan"] = lambda db: 0
    manager._locks["eod_scan"] = lock

    with pytest.raises(AlreadyRunningError):
        manager.run_now("eod_scan", MagicMock())

    lock.release()


def test_reschedule_changes_next_run_time():
    """reschedule updates the job's CronTrigger in the live scheduler."""
    manager = _make_manager()
    scheduler = BackgroundScheduler(timezone="America/New_York")

    def dummy():
        pass

    scheduler.add_job(
        dummy,
        trigger=CronTrigger(day_of_week="mon-fri", hour=16, minute=15, timezone="America/New_York"),
        id="eod_scan",
    )
    scheduler.start()
    manager._scheduler = scheduler

    try:
        manager.reschedule("eod_scan", hour=17, minute=30)
        job = scheduler.get_job("eod_scan")
        fields = {f.name: f for f in job.trigger.fields}
        assert str(fields["hour"]) == "17"
        assert str(fields["minute"]) == "30"
    finally:
        scheduler.shutdown(wait=False)


def test_pause_and_resume_job():
    """pause suspends automatic firing; resume restores it."""
    manager = _make_manager()
    scheduler = BackgroundScheduler(timezone="America/New_York")

    def dummy():
        pass

    scheduler.add_job(
        dummy,
        trigger=CronTrigger(day_of_week="mon-fri", hour=16, minute=15, timezone="America/New_York"),
        id="eod_scan",
    )
    scheduler.start()
    manager._scheduler = scheduler

    try:
        manager.pause("eod_scan")
        assert scheduler.get_job("eod_scan").next_run_time is None

        manager.resume("eod_scan")
        assert scheduler.get_job("eod_scan").next_run_time is not None
    finally:
        scheduler.shutdown(wait=False)
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/unit/api/test_schedule_manager.py -v
```
Expected: `ModuleNotFoundError: No module named 'src.api.schedule.manager'`

- [ ] **Step 3: Implement `src/api/schedule/manager.py`**

```python
"""ScheduleManager: wraps APScheduler BackgroundScheduler for the FastAPI lifespan.

Responsibilities:
- Start and stop the scheduler on app boot/shutdown.
- Register EOD and pre-close jobs from schedule_config DB rows on startup.
- Expose reschedule, pause, resume, and run_now for API route handlers.

Single-worker constraint: the FastAPI app MUST run with --workers 1.
Multiple workers would each boot their own scheduler, causing duplicate fires.
"""

import logging
import threading
from datetime import datetime
from typing import Callable, Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Maps job_id → run_type (for scanner_results queries)
JOB_RUN_TYPES = {
    "eod_scan": "eod",
    "pre_close_scan": "pre_close",
}

JOB_DISPLAY_NAMES = {
    "eod_scan": "EOD Scan",
    "pre_close_scan": "Pre-close Scan",
}


class AlreadyRunningError(Exception):
    """Raised when run_now is called while the job is already executing."""
    pass


class ScheduleManager:
    """Manages APScheduler BackgroundScheduler lifecycle and job control."""

    def __init__(self) -> None:
        self._scheduler: Optional[BackgroundScheduler] = None
        self._locks: dict[str, threading.Lock] = {}
        self._callbacks: dict[str, Callable] = {}

    def start(self, db: Session) -> None:
        """Start the BackgroundScheduler. Called from FastAPI lifespan on startup.

        Reads schedule_config rows and registers both cron jobs.
        """
        from src.db.models import ScheduleConfig
        from src.api.schedule.jobs import run_eod_job, run_pre_close_job

        job_fns: dict[str, Callable] = {
            "eod_scan": run_eod_job,
            "pre_close_scan": run_pre_close_job,
        }

        self._scheduler = BackgroundScheduler(timezone="America/New_York")

        for job_id, fn in job_fns.items():
            self._locks[job_id] = threading.Lock()
            self._callbacks[job_id] = fn

            config = db.query(ScheduleConfig).filter_by(job_id=job_id).first()
            hour = config.hour if config else (16 if job_id == "eod_scan" else 15)
            minute = config.minute if config else (15 if job_id == "eod_scan" else 45)
            enabled = config.enabled if config else True
            auto_save = config.auto_save if config else False

            self._scheduler.add_job(
                self._make_scheduled_callback(job_id, fn, auto_save),
                trigger=CronTrigger(
                    day_of_week="mon-fri",
                    hour=hour,
                    minute=minute,
                    timezone="America/New_York",
                ),
                id=job_id,
                name=JOB_DISPLAY_NAMES[job_id],
                misfire_grace_time=300,
                coalesce=True,
            )

            if not enabled:
                self._scheduler.pause_job(job_id)

        self._scheduler.start()
        logger.info("ScheduleManager started")

    def stop(self) -> None:
        """Shut down the scheduler. Called from FastAPI lifespan on shutdown."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("ScheduleManager stopped")

    def reschedule(self, job_id: str, hour: int, minute: int) -> None:
        """Update a job's CronTrigger to a new hour:minute (ET, mon-fri)."""
        if self._scheduler:
            self._scheduler.reschedule_job(
                job_id,
                trigger=CronTrigger(
                    day_of_week="mon-fri",
                    hour=hour,
                    minute=minute,
                    timezone="America/New_York",
                ),
            )

    def pause(self, job_id: str) -> None:
        """Pause a job so it does not fire on its scheduled time."""
        if self._scheduler:
            self._scheduler.pause_job(job_id)

    def resume(self, job_id: str) -> None:
        """Resume a previously paused job."""
        if self._scheduler:
            self._scheduler.resume_job(job_id)

    def run_now(self, job_id: str, db: Session) -> int:
        """Execute a job immediately in the calling thread.

        Returns the result count. Raises AlreadyRunningError if the job is
        already executing (prevents double-execution with the scheduler).
        """
        lock = self._locks[job_id]
        if not lock.acquire(blocking=False):
            raise AlreadyRunningError(job_id)
        try:
            return self._callbacks[job_id](db)
        finally:
            lock.release()

    def _make_scheduled_callback(
        self, job_id: str, fn: Callable, auto_save: bool
    ) -> Callable:
        """Return a zero-argument callback for APScheduler.

        Creates its own DB session (APScheduler runs in background threads).
        """
        def callback() -> None:
            from src.api.deps import _session_factory

            db = _session_factory()()
            try:
                lock = self._locks[job_id]
                if not lock.acquire(blocking=False):
                    logger.warning("Job %s already running; skipping scheduled fire", job_id)
                    return
                try:
                    result_count = fn(db)
                    # Re-read auto_save from DB in case it changed since startup
                    from src.db.models import ScheduleConfig
                    cfg = db.query(ScheduleConfig).filter_by(job_id=job_id).first()
                    if cfg and cfg.auto_save:
                        _auto_save_watchlist(db, job_id, result_count)
                finally:
                    lock.release()
            except Exception:
                logger.exception("Scheduled job %s failed", job_id)
            finally:
                db.close()

        return callback


def _auto_save_watchlist(db: Session, job_id: str, result_count: int) -> None:
    """Create a watchlist with results from the most recent scan run."""
    if result_count == 0:
        return

    from datetime import datetime
    from src.db.models import ScannerResult, User
    from src.api.watchlists.service import WatchlistService

    run_type = JOB_RUN_TYPES[job_id]
    display_name = JOB_DISPLAY_NAMES[job_id]

    # Find the most recent matched_at for this run_type
    latest_at = (
        db.query(ScannerResult.matched_at)
        .filter(ScannerResult.run_type == run_type)
        .order_by(ScannerResult.matched_at.desc())
        .first()
    )
    if not latest_at:
        return

    ran_at: datetime = latest_at[0]
    name = f"{display_name} — {ran_at.strftime('%b %d %H:%M')}"

    user = db.query(User).first()
    if not user:
        logger.warning("No user found; skipping auto-save watchlist")
        return

    service = WatchlistService(db)
    watchlist = service.create_watchlist(
        user_id=user.id,
        name=name,
        description=f"Auto-saved from scheduled {display_name} run",
    )

    # Add all symbols from this run
    symbols = (
        db.query(ScannerResult)
        .filter(
            ScannerResult.run_type == run_type,
            ScannerResult.matched_at >= ran_at.replace(second=0, microsecond=0),
        )
        .all()
    )
    for result in symbols:
        try:
            service.add_symbol(watchlist.id, result.stock.symbol)
        except Exception:
            logger.warning("Failed to add symbol to auto-save watchlist", exc_info=True)

    logger.info("Auto-saved watchlist '%s' with %d symbols", name, len(symbols))


# Module-level singleton used by routes and lifespan
schedule_manager = ScheduleManager()
```

- [ ] **Step 4: Run tests to confirm pass**

```bash
pytest tests/unit/api/test_schedule_manager.py -v
```
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add src/api/schedule/manager.py tests/unit/api/test_schedule_manager.py
git commit -m "feat: implement ScheduleManager with BackgroundScheduler (LIN-89)"
```

---

## Task 4: Pydantic Schemas

**Files:**
- Create: `src/api/schedule/schemas.py`
- Test: inline in integration tests (Task 6)

- [ ] **Step 1: Implement `src/api/schedule/schemas.py`**

```python
"""Pydantic schemas for the schedule API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class LastRun(BaseModel):
    ran_at: datetime
    result_count: int


class JobResponse(BaseModel):
    job_id: str
    name: str
    hour: int
    minute: int
    enabled: bool
    auto_save: bool
    last_run: Optional[LastRun] = None


class JobPatch(BaseModel):
    hour: Optional[int] = None
    minute: Optional[int] = None
    enabled: Optional[bool] = None
    auto_save: Optional[bool] = None

    @field_validator("hour")
    @classmethod
    def validate_hour(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (0 <= v <= 23):
            raise ValueError("hour must be between 0 and 23")
        return v

    @field_validator("minute")
    @classmethod
    def validate_minute(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (0 <= v <= 59):
            raise ValueError("minute must be between 0 and 59")
        return v


class RunResponse(BaseModel):
    status: str          # "ok" | "error"
    result_count: int
    detail: Optional[str] = None
```

- [ ] **Step 2: Commit**

```bash
git add src/api/schedule/schemas.py
git commit -m "feat: add schedule Pydantic schemas (LIN-90)"
```

---

## Task 5: API Routes

**Files:**
- Create: `src/api/schedule/routes.py`

- [ ] **Step 1: Implement `src/api/schedule/routes.py`**

```python
"""FastAPI routes for the schedule API.

All routes require an authenticated session (enforced by _get_user dependency).

Routes:
  GET  /api/schedule/jobs                  — list both jobs with config + last run
  PATCH /api/schedule/jobs/{job_id}        — update hour/minute/enabled/auto_save
  POST /api/schedule/jobs/{job_id}/run     — trigger job immediately
"""

import logging
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db
from src.api.schedule.manager import (
    AlreadyRunningError,
    JOB_DISPLAY_NAMES,
    JOB_RUN_TYPES,
    schedule_manager,
)
from src.api.schedule.schemas import JobPatch, JobResponse, LastRun, RunResponse
from src.db.models import ScheduleConfig, ScannerResult, User

logger = logging.getLogger(__name__)

router = APIRouter()

_JOB_IDS = list(JOB_DISPLAY_NAMES.keys())


def _get_user(request: Request, db: Session = Depends(get_db)) -> User:
    return get_current_user(request, db)


def _get_last_run(db: Session, run_type: str) -> LastRun | None:
    """Return the most recent run's ran_at and result_count from scanner_results."""
    from sqlalchemy import func as sqlfunc

    latest_at = (
        db.query(sqlfunc.max(ScannerResult.matched_at))
        .filter(ScannerResult.run_type == run_type)
        .scalar()
    )
    if not latest_at:
        return None

    count = (
        db.query(sqlfunc.count(ScannerResult.id))
        .filter(
            ScannerResult.run_type == run_type,
            func.date(ScannerResult.matched_at) == func.date(latest_at),
        )
        .scalar()
    )
    return LastRun(ran_at=latest_at, result_count=count or 0)


@router.get("", response_model=List[JobResponse])
def list_jobs(
    _user: User = Depends(_get_user),
    db: Session = Depends(get_db),
) -> List[JobResponse]:
    """Return both scheduled jobs with their current config and last run info."""
    jobs = []
    for job_id in _JOB_IDS:
        config = db.query(ScheduleConfig).filter_by(job_id=job_id).first()
        if config is None:
            # Seed defaults if migration hasn't run yet (defensive)
            config = ScheduleConfig(
                job_id=job_id,
                hour=16 if job_id == "eod_scan" else 15,
                minute=15 if job_id == "eod_scan" else 45,
            )

        run_type = JOB_RUN_TYPES[job_id]
        jobs.append(
            JobResponse(
                job_id=job_id,
                name=JOB_DISPLAY_NAMES[job_id],
                hour=config.hour,
                minute=config.minute,
                enabled=config.enabled,
                auto_save=config.auto_save,
                last_run=_get_last_run(db, run_type),
            )
        )
    return jobs


@router.patch("/{job_id}", response_model=JobResponse)
def patch_job(
    job_id: str,
    body: JobPatch,
    _user: User = Depends(_get_user),
    db: Session = Depends(get_db),
) -> JobResponse:
    """Partially update a job's config and apply changes to the live scheduler."""
    if job_id not in _JOB_IDS:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")

    config = db.query(ScheduleConfig).filter_by(job_id=job_id).first()
    if config is None:
        raise HTTPException(status_code=404, detail="schedule_config row missing; run migrations")

    # Apply partial update
    if body.hour is not None:
        config.hour = body.hour
    if body.minute is not None:
        config.minute = body.minute
    if body.enabled is not None:
        config.enabled = body.enabled
    if body.auto_save is not None:
        config.auto_save = body.auto_save
    config.updated_at = datetime.utcnow()

    try:
        db.commit()
        db.refresh(config)
    except Exception:
        db.rollback()
        logger.exception("DB commit failed for PATCH schedule/%s", job_id)
        raise HTTPException(status_code=500, detail="Failed to persist schedule change")

    # Apply to live scheduler (best-effort; DB is source of truth on next restart)
    try:
        if body.hour is not None or body.minute is not None:
            schedule_manager.reschedule(job_id, config.hour, config.minute)
        if body.enabled is not None:
            if config.enabled:
                schedule_manager.resume(job_id)
            else:
                schedule_manager.pause(job_id)
    except Exception:
        logger.exception("Live reschedule failed for %s — DB updated, restart to resync", job_id)
        # Do NOT rollback; DB is updated. Scheduler will resync on next restart.

    run_type = JOB_RUN_TYPES[job_id]
    return JobResponse(
        job_id=job_id,
        name=JOB_DISPLAY_NAMES[job_id],
        hour=config.hour,
        minute=config.minute,
        enabled=config.enabled,
        auto_save=config.auto_save,
        last_run=_get_last_run(db, run_type),
    )


@router.post("/{job_id}/run", response_model=RunResponse)
def run_job_now(
    job_id: str,
    _user: User = Depends(_get_user),
    db: Session = Depends(get_db),
) -> RunResponse:
    """Trigger a job immediately. Returns result_count. Returns 409 if already running."""
    if job_id not in _JOB_IDS:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")

    try:
        result_count = schedule_manager.run_now(job_id, db)
        return RunResponse(status="ok", result_count=result_count)
    except AlreadyRunningError:
        raise HTTPException(status_code=409, detail="Job is already running")
    except Exception:
        logger.exception("run_now failed for %s", job_id)
        return RunResponse(status="error", result_count=0, detail="Scan failed; check logs")


@router.get("/history", response_model=List[dict])
def get_history(
    _user: User = Depends(_get_user),
    db: Session = Depends(get_db),
) -> List[dict]:
    """Return last 7 days of scan runs, grouped by run_type + date, sorted desc."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    rows = (
        db.query(
            ScannerResult.run_type,
            func.date(ScannerResult.matched_at).label("run_date"),
            func.max(ScannerResult.matched_at).label("ran_at"),
            func.count(ScannerResult.id).label("result_count"),
        )
        .filter(ScannerResult.matched_at >= cutoff)
        .group_by(ScannerResult.run_type, func.date(ScannerResult.matched_at))
        .order_by(func.max(ScannerResult.matched_at).desc())
        .all()
    )

    run_type_to_name = {v: JOB_DISPLAY_NAMES[k] for k, v in JOB_RUN_TYPES.items()}
    return [
        {
            "job_name": run_type_to_name.get(r.run_type, r.run_type),
            "ran_at": r.ran_at.isoformat(),
            "result_count": r.result_count,
        }
        for r in rows
    ]
```

- [ ] **Step 2: Commit**

```bash
git add src/api/schedule/routes.py
git commit -m "feat: add /api/schedule routes (LIN-91)"
```

---

## Task 6: Wire Into FastAPI + Integration Tests

**Files:**
- Modify: `src/api/main.py`
- Create: `tests/integration/api/test_schedule.py`

- [ ] **Step 1: Write the failing integration tests**

Create `tests/integration/api/test_schedule.py`:

```python
"""Integration tests for /api/schedule routes."""

import pytest
from datetime import datetime
from unittest.mock import patch


def _seed_config(db_session):
    """Ensure schedule_config rows exist (migration already seeds them)."""
    from src.db.models import ScheduleConfig

    for job_id, hour, minute in [("eod_scan", 16, 15), ("pre_close_scan", 15, 45)]:
        if not db_session.query(ScheduleConfig).filter_by(job_id=job_id).first():
            db_session.add(ScheduleConfig(job_id=job_id, hour=hour, minute=minute))
    db_session.commit()


def test_list_jobs_returns_two_jobs(authenticated_client, db_session):
    """GET /api/schedule/jobs returns both configured jobs."""
    _seed_config(db_session)
    resp = authenticated_client.get("/api/schedule/jobs")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    job_ids = {j["job_id"] for j in data}
    assert job_ids == {"eod_scan", "pre_close_scan"}
    for job in data:
        assert "hour" in job
        assert "minute" in job
        assert "enabled" in job
        assert "auto_save" in job
        assert "last_run" in job


def test_list_jobs_requires_auth(api_client, db_session):
    """GET /api/schedule/jobs returns 401 without authentication."""
    resp = api_client.get("/api/schedule/jobs")
    assert resp.status_code == 401


def test_list_jobs_last_run_is_null_with_no_results(authenticated_client, db_session):
    """last_run is null when no scanner_results exist."""
    _seed_config(db_session)
    resp = authenticated_client.get("/api/schedule/jobs")
    assert resp.status_code == 200
    for job in resp.json():
        assert job["last_run"] is None


def test_list_jobs_last_run_populated_from_scanner_results(authenticated_client, db_session):
    """last_run reflects most recent scanner_results for the run_type."""
    from src.db.models import ScannerResult, Stock

    _seed_config(db_session)
    stock = Stock(symbol="TSLA", name="Tesla")
    db_session.add(stock)
    db_session.flush()
    db_session.add(
        ScannerResult(
            stock_id=stock.id,
            scanner_name="momentum",
            result_metadata={},
            matched_at=datetime(2026, 4, 13, 16, 15, 0),
            run_type="eod",
        )
    )
    db_session.commit()

    resp = authenticated_client.get("/api/schedule/jobs")
    assert resp.status_code == 200
    eod_job = next(j for j in resp.json() if j["job_id"] == "eod_scan")
    assert eod_job["last_run"] is not None
    assert eod_job["last_run"]["result_count"] == 1


def test_patch_job_updates_hour_and_minute(authenticated_client, db_session):
    """PATCH /api/schedule/jobs/{id} updates time fields in DB."""
    from src.api.schedule.manager import schedule_manager

    _seed_config(db_session)

    with patch.object(schedule_manager, "reschedule") as mock_reschedule:
        resp = authenticated_client.patch(
            "/api/schedule/jobs/eod_scan",
            json={"hour": 17, "minute": 0},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["hour"] == 17
    assert data["minute"] == 0
    mock_reschedule.assert_called_once_with("eod_scan", 17, 0)


def test_patch_job_validates_hour_bounds(authenticated_client, db_session):
    """PATCH returns 422 if hour is out of 0-23 range."""
    _seed_config(db_session)
    resp = authenticated_client.patch(
        "/api/schedule/jobs/eod_scan",
        json={"hour": 25},
    )
    assert resp.status_code == 422


def test_patch_job_validates_minute_bounds(authenticated_client, db_session):
    """PATCH returns 422 if minute is out of 0-59 range."""
    _seed_config(db_session)
    resp = authenticated_client.patch(
        "/api/schedule/jobs/eod_scan",
        json={"minute": 61},
    )
    assert resp.status_code == 422


def test_patch_job_unknown_id_returns_404(authenticated_client, db_session):
    """PATCH returns 404 for an unknown job_id."""
    _seed_config(db_session)
    resp = authenticated_client.patch(
        "/api/schedule/jobs/nonexistent_job",
        json={"hour": 9},
    )
    assert resp.status_code == 404


def test_run_now_returns_result_count(authenticated_client, db_session):
    """POST /run triggers the job and returns result_count."""
    from src.api.schedule.manager import schedule_manager

    _seed_config(db_session)

    with patch.object(schedule_manager, "run_now", return_value=12) as mock_run:
        resp = authenticated_client.post("/api/schedule/jobs/eod_scan/run")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["result_count"] == 12


def test_run_now_returns_409_when_already_running(authenticated_client, db_session):
    """POST /run returns 409 when the job is already executing."""
    from src.api.schedule.manager import AlreadyRunningError, schedule_manager

    _seed_config(db_session)

    with patch.object(schedule_manager, "run_now", side_effect=AlreadyRunningError("eod_scan")):
        resp = authenticated_client.post("/api/schedule/jobs/eod_scan/run")

    assert resp.status_code == 409


def test_history_returns_grouped_runs(authenticated_client, db_session):
    """GET /api/schedule/history returns runs grouped by date + run_type."""
    from src.db.models import ScannerResult, Stock

    _seed_config(db_session)
    stock = Stock(symbol="AAPL", name="Apple")
    db_session.add(stock)
    db_session.flush()
    for i in range(3):
        db_session.add(
            ScannerResult(
                stock_id=stock.id,
                scanner_name="momentum",
                result_metadata={},
                matched_at=datetime(2026, 4, 13, 16, 15, i),
                run_type="eod",
            )
        )
    db_session.commit()

    resp = authenticated_client.get("/api/schedule/history")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["result_count"] == 3
    assert data[0]["job_name"] == "EOD Scan"
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/integration/api/test_schedule.py -v 2>&1 | head -30
```
Expected: `404 Not Found` (routes not wired yet)

- [ ] **Step 3: Wire scheduler and router into `src/api/main.py`**

Replace the lifespan and create_app in `src/api/main.py`:

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
from src.api.scanners.routes import router as scanners_router
from src.api.schedule.manager import schedule_manager
from src.api.schedule.routes import router as schedule_router
from src.api.watchlists.routes import router as watchlists_router
from src.api.ws import heartbeat_loop, pubsub, ws_endpoint

FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start heartbeat + scheduler on boot; shut down cleanly."""
    from src.api.deps import get_db

    interval = float(os.environ.get("HEARTBEAT_INTERVAL", "5.0"))
    heartbeat_task = asyncio.create_task(heartbeat_loop(pubsub, interval))

    # Start scheduler with a short-lived DB session (reads schedule_config once)
    db = next(get_db())
    try:
        schedule_manager.start(db)
    finally:
        db.close()

    try:
        yield
    finally:
        heartbeat_task.cancel()
        await pubsub.close_all()
        schedule_manager.stop()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(lifespan=lifespan, title="market-data")
    app.add_middleware(SessionMiddleware)
    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(me_router, prefix="/api")
    app.include_router(settings_router, prefix="/api/settings")
    app.include_router(scanners_router, prefix="/api/scanners")
    app.include_router(schedule_router, prefix="/api/schedule/jobs")
    app.include_router(watchlists_router, prefix="/api/watchlists")
    app.add_api_websocket_route("/ws", ws_endpoint)
    if FRONTEND_DIST.exists():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
    return app
```

- [ ] **Step 4: Run integration tests**

```bash
pytest tests/integration/api/test_schedule.py -v
```
Expected: `11 passed`

- [ ] **Step 5: Run full CI to check for regressions**

```bash
make ci
```
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/api/main.py tests/integration/api/test_schedule.py
git commit -m "feat: wire ScheduleManager into lifespan and mount /api/schedule/jobs router (LIN-92)"
```

---

## Task 7: Frontend Types + API Client

**Files:**
- Create: `frontend/src/pages/schedule/types.ts`
- Create: `frontend/src/lib/schedule-api.ts`

- [ ] **Step 1: Create `frontend/src/pages/schedule/types.ts`**

```typescript
/**
 * TypeScript types for the Schedule API.
 * Matches Pydantic schemas in src/api/schedule/schemas.py
 */

export interface LastRun {
  ran_at: string;        // ISO datetime
  result_count: number;
}

export interface ScheduledJob {
  job_id: string;        // "eod_scan" | "pre_close_scan"
  name: string;          // "EOD Scan" | "Pre-close Scan"
  hour: number;          // 0–23 (ET)
  minute: number;        // 0–59
  enabled: boolean;
  auto_save: boolean;
  last_run: LastRun | null;
}

export interface JobPatch {
  hour?: number;
  minute?: number;
  enabled?: boolean;
  auto_save?: boolean;
}

export interface RunResponse {
  status: "ok" | "error";
  result_count: number;
  detail?: string;
}

export interface HistoryEntry {
  job_name: string;
  ran_at: string;        // ISO datetime
  result_count: number;
}
```

- [ ] **Step 2: Create `frontend/src/lib/schedule-api.ts`**

```typescript
/**
 * Schedule API client.
 * Provides methods for listing jobs, patching config, running jobs, and history.
 */

import { apiFetch } from "./api";
import type { ScheduledJob, JobPatch, RunResponse, HistoryEntry } from "../pages/schedule/types";

/**
 * List all scheduled jobs with their config and last run info.
 */
export const listJobs = (): Promise<ScheduledJob[]> =>
  apiFetch("/api/schedule/jobs");

/**
 * Partially update a job's config (hour, minute, enabled, auto_save).
 */
export const patchJob = (jobId: string, patch: JobPatch): Promise<ScheduledJob> =>
  apiFetch(`/api/schedule/jobs/${jobId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });

/**
 * Trigger a job to run immediately.
 */
export const runJobNow = (jobId: string): Promise<RunResponse> =>
  apiFetch(`/api/schedule/jobs/${jobId}/run`, {
    method: "POST",
  });

/**
 * Get last 7 days of scan run history, sorted descending.
 */
export const getHistory = (): Promise<HistoryEntry[]> =>
  apiFetch("/api/schedule/history");
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/schedule/types.ts frontend/src/lib/schedule-api.ts
git commit -m "feat: add schedule TypeScript types and API client (LIN-93)"
```

---

## Task 8: `JobCard` Component

**Files:**
- Create: `frontend/src/pages/schedule/job-card.tsx`

- [ ] **Step 1: Implement `frontend/src/pages/schedule/job-card.tsx`**

```tsx
/**
 * JobCard — displays a single scheduled job with inline time edit,
 * enable toggle, auto-save toggle, and a Run Now button.
 */

import { createSignal, Show } from "solid-js";
import { patchJob, runJobNow } from "../../lib/schedule-api";
import type { ScheduledJob, RunResponse } from "./types";

interface Props {
  job: ScheduledJob;
  onUpdated: (updated: ScheduledJob) => void;
}

export function JobCard(props: Props) {
  // Time edit state
  const [editingTime, setEditingTime] = createSignal(false);
  const [timeValue, setTimeValue] = createSignal(
    `${String(props.job.hour).padStart(2, "0")}:${String(props.job.minute).padStart(2, "0")}`
  );
  const [timeError, setTimeError] = createSignal<string | null>(null);

  // Run Now state
  const [running, setRunning] = createSignal(false);
  const [runResult, setRunResult] = createSignal<RunResponse | null>(null);
  const [alreadyRunning, setAlreadyRunning] = createSignal(false);

  // Toggle loading state
  const [patching, setPatching] = createSignal(false);

  async function commitTimeEdit() {
    setEditingTime(false);
    setTimeError(null);
    const [h, m] = timeValue().split(":").map(Number);
    if (isNaN(h) || isNaN(m) || h < 0 || h > 23 || m < 0 || m > 59) {
      setTimeError("Invalid time — use HH:MM (24h)");
      return;
    }
    if (h === props.job.hour && m === props.job.minute) return;
    try {
      const updated = await patchJob(props.job.job_id, { hour: h, minute: m });
      props.onUpdated(updated);
    } catch {
      setTimeError("Failed to save time — try again");
    }
  }

  async function toggleEnabled() {
    if (patching()) return;
    setPatching(true);
    try {
      const updated = await patchJob(props.job.job_id, { enabled: !props.job.enabled });
      props.onUpdated(updated);
    } finally {
      setPatching(false);
    }
  }

  async function toggleAutoSave() {
    if (patching()) return;
    setPatching(true);
    try {
      const updated = await patchJob(props.job.job_id, { auto_save: !props.job.auto_save });
      props.onUpdated(updated);
    } finally {
      setPatching(false);
    }
  }

  async function handleRunNow() {
    if (running()) return;
    setRunning(true);
    setRunResult(null);
    setAlreadyRunning(false);
    try {
      const result = await runJobNow(props.job.job_id);
      setRunResult(result);
    } catch (err: any) {
      if (err?.status === 409) {
        setAlreadyRunning(true);
      } else {
        setRunResult({ status: "error", result_count: 0, detail: "Request failed" });
      }
    } finally {
      setRunning(false);
    }
  }

  const lastRunLabel = () => {
    if (!props.job.last_run) return "No runs yet";
    const d = new Date(props.job.last_run.ran_at);
    const dateStr = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    const timeStr = d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
    return `${dateStr} ${timeStr}  ✓ ${props.job.last_run.result_count} tickers`;
  };

  return (
    <div class={`job-card ${props.job.enabled ? "enabled" : "disabled"}`}>
      <div class="job-header">
        <span class="job-name">{props.job.name}</span>
        <span class="job-schedule">Mon–Fri · {lastRunLabel()}</span>
      </div>

      <div class="job-controls">
        {/* Inline time edit */}
        <Show
          when={editingTime()}
          fallback={
            <span class="time-display" onClick={() => setEditingTime(true)}>
              {timeValue()}
            </span>
          }
        >
          <input
            type="time"
            class="time-input"
            value={timeValue()}
            onInput={e => setTimeValue(e.currentTarget.value)}
            onBlur={commitTimeEdit}
            onKeyDown={e => { if (e.key === "Enter") commitTimeEdit(); }}
            autofocus
          />
        </Show>
        <Show when={timeError()}>
          <span class="time-error">{timeError()}</span>
        </Show>

        {/* Auto-save toggle */}
        <label class="toggle-label">
          <span>Auto-save</span>
          <button
            class={`toggle ${props.job.auto_save ? "on" : "off"}`}
            onClick={toggleAutoSave}
            disabled={patching()}
            aria-label={`Auto-save ${props.job.auto_save ? "on" : "off"}`}
          />
        </label>

        {/* Run Now */}
        <button class="btn-run" onClick={handleRunNow} disabled={running()}>
          {running() ? "Running…" : "▶ Run Now"}
        </button>
        <Show when={runResult()}>
          <span class={`run-result ${runResult()!.status}`}>
            {runResult()!.status === "ok"
              ? `✓ ${runResult()!.result_count} tickers`
              : `✗ ${runResult()!.detail ?? "Failed"}`}
          </span>
        </Show>
        <Show when={alreadyRunning()}>
          <span class="run-result conflict">Already running</span>
        </Show>

        {/* Enable toggle */}
        <button
          class={`toggle ${props.job.enabled ? "on" : "off"}`}
          onClick={toggleEnabled}
          disabled={patching()}
          aria-label={`Job ${props.job.enabled ? "enabled" : "disabled"}`}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/schedule/job-card.tsx
git commit -m "feat: add JobCard component (LIN-94)"
```

---

## Task 9: Schedule Page + Route Wiring

**Files:**
- Create: `frontend/src/pages/schedule/index.tsx`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/app.tsx`

- [ ] **Step 1: Create `frontend/src/pages/schedule/index.tsx`**

```tsx
/**
 * /schedule page — shows two job cards and a 7-day run history table.
 */

import { createResource, createSignal, For, Show } from "solid-js";
import { getHistory, listJobs } from "../../lib/schedule-api";
import { JobCard } from "./job-card";
import type { HistoryEntry, ScheduledJob } from "./types";

export default function SchedulePage() {
  const [jobs, { mutate: mutateJobs }] = createResource<ScheduledJob[]>(listJobs);
  const [history] = createResource<HistoryEntry[]>(getHistory);

  function handleJobUpdated(updated: ScheduledJob) {
    mutateJobs(prev => prev?.map(j => (j.job_id === updated.job_id ? updated : j)));
  }

  function formatRanAt(isoStr: string): string {
    const d = new Date(isoStr);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" }) +
      " " + d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit", hour12: false });
  }

  return (
    <div class="schedule-page">
      <section class="jobs-section">
        <h2 class="section-title">Scheduled Jobs</h2>
        <Show when={!jobs.loading} fallback={<p>Loading…</p>}>
          <Show when={jobs()} fallback={<p>Failed to load jobs.</p>}>
            <For each={jobs()}>
              {job => <JobCard job={job} onUpdated={handleJobUpdated} />}
            </For>
          </Show>
        </Show>
      </section>

      <section class="history-section">
        <h2 class="section-title">Run History</h2>
        <Show when={!history.loading} fallback={<p>Loading…</p>}>
          <Show
            when={history() && history()!.length > 0}
            fallback={
              <p class="empty-state">
                No runs yet. Jobs will appear here after their first execution.
              </p>
            }
          >
            <table class="history-table">
              <thead>
                <tr>
                  <th>Job</th>
                  <th>Ran At (ET)</th>
                  <th>Results</th>
                </tr>
              </thead>
              <tbody>
                <For each={history()}>
                  {entry => (
                    <tr>
                      <td>{entry.job_name}</td>
                      <td>{formatRanAt(entry.ran_at)}</td>
                      <td>{entry.result_count}</td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
          </Show>
        </Show>
      </section>
    </div>
  );
}
```

- [ ] **Step 2: Add `/schedule` route to `frontend/src/main.tsx`**

Add the import after the existing `ScannerPage` import:

```typescript
import SchedulePage from "./pages/schedule/index";
```

Add the route after the `/scanners` route block:

```tsx
<Route
  path="/schedule"
  component={() => (
    <RequireAuth>
      <SchedulePage />
    </RequireAuth>
  )}
/>
```

- [ ] **Step 3: Add Schedule nav link to `frontend/src/app.tsx`**

Add after the `<A href="/scanners">Scanners</A>` line:

```tsx
<A href="/schedule">Schedule</A>
```

- [ ] **Step 4: Build frontend to verify no type errors**

```bash
cd frontend && npm run build
```
Expected: build succeeds with no TypeScript errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/schedule/index.tsx frontend/src/main.tsx frontend/src/app.tsx
git commit -m "feat: add /schedule page and nav link (LIN-95)"
```

---

## Task 10: Final Verification

- [ ] **Step 1: Run full CI**

```bash
make ci
```
Expected: all lint, type-check, and tests pass.

- [ ] **Step 2: Start the app and smoke-test manually**

```bash
# Terminal 1
cd frontend && npm run dev

# Terminal 2
uvicorn src.api.main:app --reload --workers 1
```

Navigate to `http://localhost:5173/schedule`. Verify:
- Two job cards load with default times (16:15 and 15:45)
- Auto-save toggles show as "off"
- Enable toggles show as "on"
- History table shows "No runs yet" (if no prior scans)
- Clicking the time opens an inline edit input
- Changing the time and blurring sends a PATCH and updates the card

- [ ] **Step 3: Update the frontend roadmap**

In `docs/superpowers/specs/2026-04-08-frontend-roadmap.md`, mark items 3 and 4 as complete:

```markdown
- [x] 3. Scanner control panel — *complete (2026-04-14)*
- [x] 4. Scheduler UI — *complete (2026-04-14)*
```

- [ ] **Step 4: Final commit**

```bash
git add docs/superpowers/specs/2026-04-08-frontend-roadmap.md
git commit -m "chore: mark scanner control panel and scheduler UI complete in roadmap"
```

---

## Self-Review Notes

**Spec coverage check:**
- ✅ §3 job cards — Tasks 8, 9
- ✅ §3 inline time edit — Task 8 (`JobCard`)
- ✅ §3 auto-save toggle off by default — seeded `auto_save=false` in Task 1
- ✅ §3 auto-save naming `{Job} — {Date} {HH:MM}` — `_auto_save_watchlist` in Task 3
- ✅ §3 run now with inline spinner + 409 — Task 8, Task 6 test
- ✅ §3 enable toggle — Task 8
- ✅ §3 history table sorted desc — `ORDER BY` in routes Task 5
- ✅ §3 empty state — Task 9 fallback `<Show>`
- ✅ §4 `schedule_config` table + seed — Task 1
- ✅ §5 `BackgroundScheduler` in lifespan — Task 6 (`main.py`)
- ✅ §5 `America/New_York` hardcoded — Tasks 3, 5
- ✅ §5 `mon-fri` hardcoded — Tasks 3, 5
- ✅ §5 single-worker constraint — documented in `manager.py` docstring
- ✅ §6 auth — `_get_user` dep on every route
- ✅ §6 PATCH validation h/m bounds — `JobPatch` validators + test
- ✅ §6 PATCH mid-run disable — let run finish, pause before next fire (APScheduler behavior)
- ✅ §6 PATCH rollback on scheduler failure — try/except in routes Task 5
- ✅ §6 `updated_at` written on PATCH — `config.updated_at = datetime.utcnow()`
- ✅ §8 all frontend files created/modified — Tasks 7, 8, 9
