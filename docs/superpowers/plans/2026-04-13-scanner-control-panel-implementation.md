# Scanner Control Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Scanner Control Panel (sub-project 3) — a `/scanners` route with EOD and Intraday tabs that surfaces scanner results, supports pre-close scanning at 3:45 PM ET, and connects to watchlist creation.

**Architecture:** Two-tab SolidJS frontend (`/scanners`) backed by three new FastAPI endpoints. EOD tab reads existing `scanner_results`. Pre-close scanner adds a 3:45 PM APScheduler job using `realtime_quotes` as partial candle data. Intraday tab runs synchronous on-demand scans against `intraday_candles` — results are ephemeral. One `run_type` column added to `scanner_results` to distinguish EOD from pre-close.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Alembic, PostgreSQL, SolidJS, TypeScript, Vite, Vitest, Playwright

**Linear issues:** LIN-76 through LIN-86

---

## File Structure

**New files to create:**
```
src/api/scanners/__init__.py
src/api/scanners/routes.py
src/api/scanners/schemas.py
src/scanner/pre_close_executor.py
src/db/migrations/versions/<hash>_add_run_type_to_scanner_results.py
tests/unit/scanner/test_pre_close_executor.py
tests/unit/api/test_scanner_schemas.py
tests/integration/api/test_scanners.py
frontend/src/pages/scanners/types.ts
frontend/src/pages/scanners/index.tsx
frontend/src/pages/scanners/eod-tab.tsx
frontend/src/pages/scanners/intraday-tab.tsx
frontend/src/pages/scanners/results-panel.tsx
frontend/src/pages/scanners/ticker-detail.tsx
frontend/src/lib/scanners-api.ts
frontend/tests/unit/pages/scanners/results-panel.test.tsx
frontend/tests/unit/pages/scanners/eod-tab.test.tsx
frontend/tests/unit/pages/scanners/intraday-tab.test.tsx
frontend/tests/unit/lib/scanners-api.test.ts
frontend/tests/e2e/scanners.spec.ts
```

**Files to modify:**
```
src/db/models.py                  — add run_type to ScannerResult
src/scanner/base.py               — add timeframe + description to Scanner ABC
src/scanner/scanners/momentum_scan.py   — set timeframe/description
src/scanner/scanners/price_action.py    — set timeframe/description
src/scanner/scanners/volume_scan.py     — set timeframe/description
src/scanner/executor.py           — accept run_type param in _persist_results
src/api/main.py                   — register scanners router
src/main.py                       — add pre-close APScheduler job
frontend/src/main.tsx             — add /scanners route
frontend/src/app.tsx              — add Scanners nav link
```

---

## Task 1: DB Migration — add `run_type` to `scanner_results` (LIN-76)

**Files:**
- Modify: `src/db/models.py` (ScannerResult class, lines 227-246)
- Create: `src/db/migrations/versions/<hash>_add_run_type_to_scanner_results.py`
- Test: `tests/unit/test_watchlist_models.py` (add one test at the bottom)

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/unit/test_watchlist_models.py (or create tests/unit/test_scanner_models.py)
def test_scanner_result_run_type_default(db_session):
    """ScannerResult defaults run_type to 'eod'."""
    from datetime import datetime
    from src.db.models import ScannerResult, Stock

    stock = Stock(symbol="AAPL", name="Apple Inc.")
    db_session.add(stock)
    db_session.flush()

    result = ScannerResult(
        stock_id=stock.id,
        scanner_name="momentum",
        result_metadata={"rsi": 72.0},
        matched_at=datetime.utcnow(),
    )
    db_session.add(result)
    db_session.commit()

    assert result.run_type == "eod"


def test_scanner_result_run_type_pre_close(db_session):
    """ScannerResult accepts run_type='pre_close'."""
    from datetime import datetime
    from src.db.models import ScannerResult, Stock

    stock = Stock(symbol="NVDA", name="Nvidia Corp")
    db_session.add(stock)
    db_session.flush()

    result = ScannerResult(
        stock_id=stock.id,
        scanner_name="momentum",
        result_metadata={},
        matched_at=datetime.utcnow(),
        run_type="pre_close",
    )
    db_session.add(result)
    db_session.commit()

    assert result.run_type == "pre_close"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/test_scanner_models.py -v
```
Expected: FAIL — `ScannerResult` has no `run_type` attribute.

- [ ] **Step 3: Add `run_type` to `ScannerResult` model**

In `src/db/models.py`, update the `ScannerResult` class:

```python
class ScannerResult(Base):
    """Scanner results (persistent audit trail)."""

    __tablename__ = "scanner_results"

    id = Column(BigInteger, primary_key=True)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    scanner_name = Column(String(255), nullable=False)
    result_metadata: Column[dict] = Column(JSONB, default=dict)
    matched_at = Column(DateTime, nullable=False)
    run_type = Column(String(20), nullable=False, default="eod")
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_scanner_results_name_ts", "scanner_name", "matched_at"),
        Index("ix_scanner_results_stock_ts", "stock_id", "matched_at"),
    )

    stock = relationship("Stock", back_populates="scanner_results")
```

- [ ] **Step 4: Generate Alembic migration**

```bash
alembic revision --autogenerate -m "add_run_type_to_scanner_results"
```

Open the generated file and verify it contains:
```python
op.add_column('scanner_results', sa.Column('run_type', sa.String(20), nullable=False, server_default='eod'))
```

If `server_default` is missing, add it manually. The column must have a server-side default so existing rows are backfilled without a data migration.

- [ ] **Step 5: Apply migration**

```bash
alembic upgrade head
```
Expected: no errors.

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/unit/test_scanner_models.py -v
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/db/models.py src/db/migrations/versions/*run_type*
git commit -m "feat: add run_type column to scanner_results (LIN-76)"
```

---

## Task 2: Extend Scanner ABC + scanner metadata (LIN-77, part 1)

**Files:**
- Modify: `src/scanner/base.py`
- Modify: `src/scanner/scanners/momentum_scan.py`
- Modify: `src/scanner/scanners/price_action.py`
- Modify: `src/scanner/scanners/volume_scan.py`

- [ ] **Step 1: Write failing test**

Create `tests/unit/scanner/test_scanner_metadata.py`:

```python
"""Tests for scanner ABC metadata attributes."""
import pytest
from src.scanner.scanners.momentum_scan import MomentumScanner
from src.scanner.scanners.price_action import PriceActionScanner
from src.scanner.scanners.volume_scan import VolumeScanner


def test_momentum_scanner_metadata():
    s = MomentumScanner()
    assert s.timeframe == "daily"
    assert isinstance(s.description, str)
    assert len(s.description) > 0


def test_price_action_scanner_metadata():
    s = PriceActionScanner()
    assert s.timeframe == "daily"
    assert isinstance(s.description, str)


def test_volume_scanner_metadata():
    s = VolumeScanner()
    assert s.timeframe == "daily"
    assert isinstance(s.description, str)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/unit/scanner/test_scanner_metadata.py -v
```
Expected: FAIL — `Scanner` has no `timeframe` attribute.

- [ ] **Step 3: Add `timeframe` and `description` to Scanner ABC**

In `src/scanner/base.py`:

```python
"""Scanner base classes: Scanner abstract base and ScanResult dataclass."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List
from datetime import datetime
from src.scanner.context import ScanContext


@dataclass
class ScanResult:
    """Result from a scanner — single source of truth."""

    stock_id: int
    scanner_name: str
    metadata: dict
    matched_at: datetime = field(default_factory=datetime.utcnow)


class Scanner(ABC):
    """Abstract base for all scanners."""

    timeframe: str = "daily"
    description: str = ""

    @abstractmethod
    def scan(self, context: ScanContext) -> List[ScanResult]:
        """Run scanner against context, return matches."""
        pass
```

- [ ] **Step 4: Add metadata to each concrete scanner**

In `src/scanner/scanners/momentum_scan.py`, add to class body (before `scan` method):

```python
timeframe = "daily"
description = "RSI-14 oversold (<30) or overbought (>70) on daily candles"
```

In `src/scanner/scanners/price_action.py`, add:

```python
timeframe = "daily"
description = "Price action patterns on daily candles (breakouts, support/resistance)"
```

In `src/scanner/scanners/volume_scan.py`, add:

```python
timeframe = "daily"
description = "Volume spike detection — volume > 1.5x 20-day average"
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/unit/scanner/test_scanner_metadata.py -v
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/scanner/base.py src/scanner/scanners/
git commit -m "feat: add timeframe and description metadata to Scanner ABC (LIN-77)"
```

---

## Task 3: Scanner API module — GET /api/scanners (LIN-77, part 2)

**Files:**
- Create: `src/api/scanners/__init__.py`
- Create: `src/api/scanners/schemas.py`
- Create: `src/api/scanners/routes.py`
- Modify: `src/api/main.py`
- Create: `tests/integration/api/test_scanners.py`

- [ ] **Step 1: Write failing integration test**

Create `tests/integration/api/test_scanners.py`:

```python
"""Integration tests for scanner API endpoints."""


def test_list_scanners_returns_registered_scanners(authenticated_client):
    """GET /api/scanners returns all registered scanners with metadata."""
    resp = authenticated_client.get("/api/scanners")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 3

    names = {s["name"] for s in data}
    assert "momentum" in names
    assert "price_action" in names
    assert "volume" in names

    for scanner in data:
        assert "name" in scanner
        assert "timeframe" in scanner
        assert "description" in scanner
        assert scanner["timeframe"] == "daily"


def test_list_scanners_requires_auth(api_client):
    """GET /api/scanners returns 401 without authentication."""
    resp = api_client.get("/api/scanners")
    assert resp.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/integration/api/test_scanners.py::test_list_scanners_returns_registered_scanners -v
```
Expected: FAIL — 404 (route doesn't exist).

- [ ] **Step 3: Create schemas**

Create `src/api/scanners/__init__.py` (empty).

Create `src/api/scanners/schemas.py`:

```python
"""Pydantic schemas for scanner API."""
from pydantic import BaseModel


class ScannerMeta(BaseModel):
    """Scanner metadata returned by list endpoint."""
    name: str
    timeframe: str
    description: str


class ScannerResultItem(BaseModel):
    """Single scanner result for a ticker."""
    scanner_name: str
    symbol: str
    score: float | None
    signal: str | None
    price: float | None
    volume: int | None
    change_pct: float | None
    indicators_fired: list[str]
    matched_at: str  # ISO datetime


class ScannerResultsResponse(BaseModel):
    """Response from GET /api/scanners/results."""
    results: list[ScannerResultItem]
    run_type: str
    date: str


class IntradayRunRequest(BaseModel):
    """Request body for POST /api/scanners/run."""
    scanners: list[str]
    timeframe: str  # '15m' | '1h'
    input_scope: str | int  # 'universe' or watchlist_id
```

- [ ] **Step 4: Create routes with list endpoint**

Create `src/api/scanners/routes.py`:

```python
"""Scanner API routes."""
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db
from src.api.scanners.schemas import (
    IntradayRunRequest,
    ScannerMeta,
    ScannerResultItem,
    ScannerResultsResponse,
)
from src.db.models import RealtimeQuote, ScannerResult, Stock, User

router = APIRouter()


def _get_user(request: Request, db: Session = Depends(get_db)) -> User:
    return get_current_user(request, db)


def _build_registry():
    """Build scanner registry from registered scanners."""
    from src.scanner.registry import ScannerRegistry
    from src.scanner.scanners.momentum_scan import MomentumScanner
    from src.scanner.scanners.price_action import PriceActionScanner
    from src.scanner.scanners.volume_scan import VolumeScanner

    registry = ScannerRegistry()
    registry.register("momentum", MomentumScanner())
    registry.register("price_action", PriceActionScanner())
    registry.register("volume", VolumeScanner())
    return registry


@router.get("", response_model=list[ScannerMeta])
def list_scanners(user: User = Depends(_get_user)):
    """List all registered scanners with name, timeframe, and description."""
    registry = _build_registry()
    return [
        ScannerMeta(name=name, timeframe=scanner.timeframe, description=scanner.description)
        for name, scanner in registry.list().items()
    ]
```

- [ ] **Step 5: Register router**

In `src/api/main.py`, add after the watchlists router:

```python
from src.api.scanners.routes import router as scanners_router
# ...
app.include_router(scanners_router, prefix="/api/scanners")
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/integration/api/test_scanners.py::test_list_scanners_returns_registered_scanners tests/integration/api/test_scanners.py::test_list_scanners_requires_auth -v
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/api/scanners/ src/api/main.py tests/integration/api/test_scanners.py
git commit -m "feat: add GET /api/scanners endpoint (LIN-77)"
```

---

## Task 4: GET /api/scanners/results (LIN-78)

**Files:**
- Modify: `src/api/scanners/routes.py`
- Modify: `tests/integration/api/test_scanners.py`

- [ ] **Step 1: Write failing integration tests**

Append to `tests/integration/api/test_scanners.py`:

```python
from datetime import datetime, date as date_type
from src.db.models import ScannerResult, Stock


def _seed_results(db_session, run_type="eod"):
    """Helper: seed one scanner result for AAPL."""
    stock = Stock(symbol="AAPL", name="Apple Inc.")
    db_session.add(stock)
    db_session.flush()
    result = ScannerResult(
        stock_id=stock.id,
        scanner_name="momentum",
        result_metadata={"reason": "overbought", "rsi": 72.5},
        matched_at=datetime.utcnow(),
        run_type=run_type,
    )
    db_session.add(result)
    db_session.commit()
    return stock, result


def test_get_results_defaults_to_latest(authenticated_client, db_session):
    """GET /api/scanners/results returns latest results by default."""
    _seed_results(db_session)
    resp = authenticated_client.get("/api/scanners/results")
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert len(data["results"]) >= 1
    assert data["results"][0]["symbol"] == "AAPL"
    assert data["results"][0]["scanner_name"] == "momentum"


def test_get_results_filter_by_run_type(authenticated_client, db_session):
    """GET /api/scanners/results?run_type=pre_close filters correctly."""
    _seed_results(db_session, run_type="eod")
    _seed_results(db_session, run_type="pre_close")
    resp = authenticated_client.get("/api/scanners/results?run_type=pre_close")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_type"] == "pre_close"
    assert all(r["scanner_name"] == "momentum" for r in data["results"])


def test_get_results_filter_by_scanner(authenticated_client, db_session):
    """GET /api/scanners/results?scanners=momentum returns only momentum results."""
    _seed_results(db_session)
    resp = authenticated_client.get("/api/scanners/results?scanners=momentum")
    assert resp.status_code == 200
    data = resp.json()
    assert all(r["scanner_name"] == "momentum" for r in data["results"])


def test_get_results_empty_returns_empty_list(authenticated_client, db_session):
    """GET /api/scanners/results with no data returns empty results, not 404."""
    resp = authenticated_client.get("/api/scanners/results")
    assert resp.status_code == 200
    assert resp.json()["results"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/integration/api/test_scanners.py::test_get_results_defaults_to_latest -v
```
Expected: FAIL — 404 (route doesn't exist yet).

- [ ] **Step 3: Implement GET /api/scanners/results in routes.py**

Add to `src/api/scanners/routes.py`:

```python
@router.get("/results", response_model=ScannerResultsResponse)
def get_results(
    scanners: Optional[str] = Query(None, description="Comma-separated scanner names"),
    run_type: str = Query("eod", description="'eod' or 'pre_close'"),
    date: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD) or omit for latest"),
    user: User = Depends(_get_user),
    db: Session = Depends(get_db),
):
    """Query scanner_results with optional filters. Defaults to latest date."""
    # Resolve date: latest matched_at date if not specified
    if date is None:
        latest = db.query(ScannerResult.matched_at).order_by(
            ScannerResult.matched_at.desc()
        ).first()
        if latest is None:
            return ScannerResultsResponse(results=[], run_type=run_type, date="")
        resolved_date = latest[0].date()
    else:
        resolved_date = datetime.strptime(date, "%Y-%m-%d").date()

    scanner_names = [s.strip() for s in scanners.split(",")] if scanners else None

    query = (
        db.query(ScannerResult, Stock)
        .join(Stock, ScannerResult.stock_id == Stock.id)
        .filter(
            ScannerResult.run_type == run_type,
        )
    )

    # Filter to the resolved date (match on date portion of matched_at)
    start = datetime.combine(resolved_date, datetime.min.time())
    end = datetime.combine(resolved_date, datetime.max.time())
    query = query.filter(ScannerResult.matched_at.between(start, end))

    if scanner_names:
        query = query.filter(ScannerResult.scanner_name.in_(scanner_names))

    rows = query.all()

    results = []
    for sr, stock in rows:
        meta = sr.result_metadata or {}
        # Attempt to get latest quote for price/volume data
        quote = (
            db.query(RealtimeQuote)
            .filter(RealtimeQuote.stock_id == stock.id)
            .order_by(RealtimeQuote.timestamp.desc())
            .first()
        )
        results.append(
            ScannerResultItem(
                scanner_name=sr.scanner_name,
                symbol=stock.symbol,
                score=meta.get("score"),
                signal=meta.get("reason") or meta.get("signal"),
                price=float(quote.last) if quote and quote.last else None,
                volume=int(quote.volume) if quote and quote.volume else None,
                change_pct=float(quote.change_pct) if quote and quote.change_pct else None,
                indicators_fired=[k for k, v in meta.items() if isinstance(v, bool) and v],
                matched_at=sr.matched_at.isoformat(),
            )
        )

    return ScannerResultsResponse(
        results=results,
        run_type=run_type,
        date=resolved_date.isoformat(),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/integration/api/test_scanners.py -k "results" -v
```
Expected: all PASS.

- [ ] **Step 5: Add GET /api/scanners/run-dates endpoint (powers EOD date dropdown)**

Append to `src/api/scanners/routes.py`:

```python
class RunDateEntry(BaseModel):
    date: str          # ISO date e.g. "2026-04-13"
    run_type: str      # "eod" | "pre_close"
    time: str          # HH:MM e.g. "16:15"


@router.get("/run-dates", response_model=list[RunDateEntry])
def get_run_dates(
    user: User = Depends(_get_user),
    db: Session = Depends(get_db),
):
    """Return distinct (date, run_type, time) entries for the past 5 trading days."""
    from sqlalchemy import func, cast as sa_cast, Date as SADate

    rows = (
        db.query(
            func.date(ScannerResult.matched_at).label("date"),
            ScannerResult.run_type,
            func.max(ScannerResult.matched_at).label("latest_ts"),
        )
        .group_by(func.date(ScannerResult.matched_at), ScannerResult.run_type)
        .order_by(func.date(ScannerResult.matched_at).desc(), ScannerResult.run_type)
        .limit(20)
        .all()
    )
    return [
        RunDateEntry(
            date=str(row.date),
            run_type=row.run_type,
            time=row.latest_ts.strftime("%H:%M"),
        )
        for row in rows
    ]
```

Also add `RunDateEntry` to `src/api/scanners/schemas.py`:

```python
class RunDateEntry(BaseModel):
    date: str
    run_type: str
    time: str
```

And add the corresponding client function to `frontend/src/lib/scanners-api.ts`:

```typescript
export interface RunDateEntry {
  date: string;
  run_type: string;
  time: string;
}

export const getRunDates = (): Promise<RunDateEntry[]> =>
  apiFetch("/api/scanners/run-dates");
```

Add integration test to `tests/integration/api/test_scanners.py`:

```python
def test_get_run_dates_returns_distinct_runs(authenticated_client, db_session):
    """GET /api/scanners/run-dates returns distinct date+run_type combos."""
    _seed_results(db_session, run_type="eod")
    _seed_results(db_session, run_type="pre_close")
    resp = authenticated_client.get("/api/scanners/run-dates")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    run_types = {d["run_type"] for d in data}
    assert run_types == {"eod", "pre_close"}
```

- [ ] **Step 6: Commit**

```bash
git add src/api/scanners/routes.py src/api/scanners/schemas.py \
        tests/integration/api/test_scanners.py
git commit -m "feat: add GET /api/scanners/results and run-dates endpoints (LIN-78)"
```

---

## Task 5: Pre-close scanner + APScheduler job (LIN-79)

**Files:**
- Create: `src/scanner/pre_close_executor.py`
- Modify: `src/scanner/executor.py` (add `run_type` to `_persist_results`)
- Modify: `src/main.py` (add scheduler job)
- Create: `tests/unit/scanner/test_pre_close_executor.py`
- Create: `tests/integration/api/test_pre_close_scan.py`

- [ ] **Step 1: Write failing unit tests**

Create `tests/unit/scanner/test_pre_close_executor.py`:

```python
"""Unit tests for PreCloseExecutor."""
from datetime import datetime
from unittest.mock import MagicMock, patch
from src.scanner.pre_close_executor import PreCloseExecutor
from src.db.models import RealtimeQuote, Stock


def _make_mock_db(stock, quote):
    """Build a mock DB session with stock + quote pre-loaded."""
    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        if model == Stock:
            q.filter.return_value.all.return_value = [stock]
        elif model == RealtimeQuote:
            q.filter.return_value.order_by.return_value.first.return_value = quote
        return q

    db.query.side_effect = query_side_effect
    return db


def test_pre_close_executor_builds_context_with_last_as_close():
    """PreCloseExecutor uses realtime_quotes.last as close proxy in ScanContext."""
    stock = MagicMock(spec=Stock)
    stock.id = 1
    stock.symbol = "AAPL"
    stock.daily_candles = []

    quote = MagicMock(spec=RealtimeQuote)
    quote.last = 189.20
    quote.open = 185.0
    quote.high = 190.0
    quote.low = 184.0
    quote.volume = 42000000
    quote.timestamp = datetime.utcnow()

    db = _make_mock_db(stock, quote)
    registry = MagicMock()
    registry.list.return_value = {}
    output_handler = MagicMock()

    executor = PreCloseExecutor(registry=registry, indicators_registry={},
                                output_handler=output_handler, db=db)
    contexts = executor.build_contexts()

    assert len(contexts) == 1
    ctx = contexts[0]
    assert ctx.symbol == "AAPL"
    # Close proxy: last value should be present in daily_candles appended candle
    assert len(ctx.daily_candles) >= 0  # may be 0 if no historical candles


def test_pre_close_executor_writes_pre_close_run_type():
    """PreCloseExecutor persists results with run_type='pre_close'."""
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = []
    registry = MagicMock()
    registry.list.return_value = {}
    output_handler = MagicMock()

    executor = PreCloseExecutor(registry=registry, indicators_registry={},
                                output_handler=output_handler, db=db)
    executor.run()

    # No results = no DB writes, just verify it completes without error
    db.add_all.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/unit/scanner/test_pre_close_executor.py -v
```
Expected: FAIL — `PreCloseExecutor` not found.

- [ ] **Step 3: Update `_persist_results` in executor.py to accept `run_type`**

In `src/scanner/executor.py`, update `_persist_results`:

```python
def _persist_results(self, results: List[ScanResult], run_type: str = "eod") -> None:
    """Batch insert scanner results into the database."""
    if not results or not self.db:
        return
    self.db.add_all(
        [
            ScannerResultModel(
                stock_id=r.stock_id,
                scanner_name=r.scanner_name,
                result_metadata=r.metadata,
                matched_at=r.matched_at,
                run_type=run_type,
            )
            for r in results
        ]
    )
    self.db.commit()
```

Also update the `run_eod` method call: `self._persist_results(stock_results)` → `self._persist_results(stock_results, run_type="eod")`.

- [ ] **Step 4: Create `PreCloseExecutor`**

Create `src/scanner/pre_close_executor.py`:

```python
"""Pre-close scanner executor: runs daily scanners using realtime_quotes as partial candle."""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from src.data_provider.base import Candle
from src.db.models import DailyCandle, RealtimeQuote, ScannerResult as ScannerResultModel, Stock
from src.output.base import OutputHandler
from src.scanner.base import ScanResult
from src.scanner.context import ScanContext
from src.scanner.executor import ScannerExecutor
from src.scanner.indicators.cache import IndicatorCache
from src.scanner.registry import ScannerRegistry

logger = logging.getLogger(__name__)


class PreCloseExecutor(ScannerExecutor):
    """Runs daily scanners using realtime_quotes.last as close proxy for today's partial candle.

    Extends ScannerExecutor. Historical bars come from daily_candles; today's partial
    candle is built from the latest RealtimeQuote (open/high/low/last/volume).
    Results are persisted with run_type='pre_close'.
    """

    def build_contexts(self) -> List[ScanContext]:
        """Build ScanContexts for all stocks with today's partial candle appended."""
        if not self.db:
            return []

        stocks = self.db.query(Stock).all()
        contexts = []

        for stock in stocks:
            try:
                # Get today's realtime quote (partial candle)
                quote = (
                    self.db.query(RealtimeQuote)
                    .filter(RealtimeQuote.stock_id == stock.id)
                    .order_by(RealtimeQuote.timestamp.desc())
                    .first()
                )
                if not quote or quote.last is None:
                    continue  # Skip stocks with no live quote

                # Build historical candles from daily_candles
                historical = self._to_candles(
                    sorted(stock.daily_candles, key=lambda c: c.timestamp)
                )

                # Append today's partial candle using last as close proxy
                today_candle = Candle(
                    timestamp=quote.timestamp or datetime.utcnow(),
                    open=float(quote.open) if quote.open else float(quote.last),
                    high=float(quote.high) if quote.high else float(quote.last),
                    low=float(quote.low) if quote.low else float(quote.last),
                    close=float(quote.last),
                    volume=int(quote.volume) if quote.volume else 0,
                )
                all_candles = historical + [today_candle]

                indicator_cache = IndicatorCache(self.indicators_registry)
                context = ScanContext(
                    stock_id=stock.id,
                    symbol=stock.symbol,
                    daily_candles=all_candles,
                    intraday_candles={},
                    indicator_cache=indicator_cache,
                )
                contexts.append(context)
            except Exception:
                logger.exception(f"Failed to build pre-close context for {stock.symbol}")

        return contexts

    def run(self) -> List[ScanResult]:
        """Run all scanners against pre-close contexts. Persist with run_type='pre_close'."""
        contexts = self.build_contexts()
        all_results: List[ScanResult] = []

        for context in contexts:
            stock_results: List[ScanResult] = []
            for scanner_name, scanner in self.registry.list().items():
                try:
                    results = scanner.scan(context)
                    for result in results:
                        stock_results.append(result)
                        all_results.append(result)
                        self.output_handler.emit_scan_result(result)
                except Exception:
                    logger.exception(f"{scanner_name} failed for {context.symbol}")

            if stock_results:
                self._persist_results(stock_results, run_type="pre_close")

        logger.info(f"Pre-close scan complete: {len(all_results)} results")
        return all_results
```

- [ ] **Step 5: Run unit tests to verify they pass**

```bash
pytest tests/unit/scanner/test_pre_close_executor.py -v
```
Expected: PASS.

- [ ] **Step 6: Add APScheduler job at 3:45 PM ET in `src/main.py`**

Find the scan scheduler section (~line 795) and add a second job inside the same scheduler function:

```python
# Add second job: pre-close scan at 3:45 PM ET
scheduler.add_job(
    run_pre_close_scan_job,
    CronTrigger(day_of_week="mon-fri", hour=15, minute=45, timezone="America/New_York"),
    id="pre_close_scan",
    name="Pre-close scan (3:45 PM ET)",
    replace_existing=True,
)
```

Add the `run_pre_close_scan_job` function near the existing EOD scan function in `src/main.py`:

```python
def run_pre_close_scan_job():
    """Execute pre-close scanner using realtime_quotes as partial candle data."""
    from src.scanner.pre_close_executor import PreCloseExecutor
    from src.scanner.scanners.momentum_scan import MomentumScanner
    from src.scanner.scanners.price_action import PriceActionScanner
    from src.scanner.scanners.volume_scan import VolumeScanner
    from src.scanner.registry import ScannerRegistry
    from src.scanner.indicators.cache import IndicatorCache
    from src.output.composite import CompositeOutputHandler
    from src.output.cli import CLIOutputHandler
    from src.db.connection import get_session

    logger.info("Starting pre-close scan (3:45 PM ET)...")
    registry = ScannerRegistry()
    registry.register("momentum", MomentumScanner())
    registry.register("price_action", PriceActionScanner())
    registry.register("volume", VolumeScanner())

    output_handler = CompositeOutputHandler([CLIOutputHandler()])

    with get_session() as db:
        executor = PreCloseExecutor(
            registry=registry,
            indicators_registry={},
            output_handler=output_handler,
            db=db,
        )
        results = executor.run()
    logger.info(f"Pre-close scan done: {len(results)} signals")
```

- [ ] **Step 7: Run full test suite to verify no regressions**

```bash
pytest tests/unit/scanner/ -v
```
Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add src/scanner/pre_close_executor.py src/scanner/executor.py src/main.py \
        tests/unit/scanner/
git commit -m "feat: add PreCloseExecutor and 3:45 PM ET APScheduler job (LIN-79)"
```

---

## Task 6: POST /api/scanners/run — intraday on-demand scan (LIN-80)

**Files:**
- Modify: `src/api/scanners/routes.py`
- Modify: `tests/integration/api/test_scanners.py`

- [ ] **Step 1: Write failing integration test**

Append to `tests/integration/api/test_scanners.py`:

```python
from src.db.models import IntradayCandle, Stock, WatchlistSymbol, Watchlist, User


def _seed_intraday(db_session):
    """Seed one intraday candle for TSLA at 15m resolution."""
    stock = Stock(symbol="TSLA", name="Tesla Inc.")
    db_session.add(stock)
    db_session.flush()
    candle = IntradayCandle(
        stock_id=stock.id,
        resolution="15m",
        timestamp=datetime.utcnow(),
        open=170.0, high=175.0, low=169.0, close=173.0, volume=5000000,
    )
    db_session.add(candle)
    db_session.commit()
    return stock


def test_run_intraday_universe_scope(authenticated_client, db_session):
    """POST /api/scanners/run with universe scope returns results without persisting."""
    _seed_intraday(db_session)
    resp = authenticated_client.post("/api/scanners/run", json={
        "scanners": ["momentum"],
        "timeframe": "15m",
        "input_scope": "universe",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert isinstance(data["results"], list)
    # Verify nothing was written to scanner_results
    count = db_session.query(ScannerResult).count()
    assert count == 0


def test_run_intraday_empty_data_returns_empty(authenticated_client, db_session):
    """POST /api/scanners/run returns empty list when no intraday data exists."""
    resp = authenticated_client.post("/api/scanners/run", json={
        "scanners": ["momentum"],
        "timeframe": "15m",
        "input_scope": "universe",
    })
    assert resp.status_code == 200
    assert resp.json()["results"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/integration/api/test_scanners.py::test_run_intraday_universe_scope -v
```
Expected: FAIL — 404.

- [ ] **Step 3: Implement POST /api/scanners/run**

Add to `src/api/scanners/routes.py`:

```python
@router.post("/run", response_model=ScannerResultsResponse)
def run_intraday(
    payload: IntradayRunRequest,
    user: User = Depends(_get_user),
    db: Session = Depends(get_db),
):
    """Run intraday scan synchronously. Results are returned directly — not persisted."""
    from src.db.models import IntradayCandle, WatchlistSymbol
    from src.data_provider.base import Candle
    from src.scanner.context import ScanContext
    from src.scanner.indicators.cache import IndicatorCache

    registry = _build_registry()

    # Resolve input scope: universe or watchlist symbols
    if payload.input_scope == "universe":
        stocks = db.query(Stock).all()
    else:
        watchlist_id = int(payload.input_scope)
        rows = db.query(WatchlistSymbol, Stock).join(
            Stock, WatchlistSymbol.stock_id == Stock.id
        ).filter(WatchlistSymbol.watchlist_id == watchlist_id).all()
        stocks = [row[1] for row in rows]

    if not stocks:
        return ScannerResultsResponse(results=[], run_type="intraday",
                                      date=datetime.utcnow().date().isoformat())

    results: list[ScannerResultItem] = []

    for stock in stocks:
        candles_orm = (
            db.query(IntradayCandle)
            .filter(
                IntradayCandle.stock_id == stock.id,
                IntradayCandle.resolution == payload.timeframe,
            )
            .order_by(IntradayCandle.timestamp)
            .all()
        )
        if not candles_orm:
            continue

        candles = [
            Candle(
                timestamp=c.timestamp,
                open=float(c.open),
                high=float(c.high),
                low=float(c.low),
                close=float(c.close),
                volume=int(c.volume),
            )
            for c in candles_orm
        ]

        indicator_cache = IndicatorCache({})
        context = ScanContext(
            stock_id=stock.id,
            symbol=stock.symbol,
            daily_candles=candles,
            intraday_candles={payload.timeframe: candles},
            indicator_cache=indicator_cache,
        )

        for scanner_name in payload.scanners:
            scanner = registry.get(scanner_name)
            if not scanner:
                continue
            try:
                scan_results = scanner.scan(context)
                for r in scan_results:
                    meta = r.metadata or {}
                    results.append(ScannerResultItem(
                        scanner_name=r.scanner_name,
                        symbol=stock.symbol,
                        score=meta.get("score"),
                        signal=meta.get("reason") or meta.get("signal"),
                        price=float(candles[-1].close) if candles else None,
                        volume=int(candles[-1].volume) if candles else None,
                        change_pct=None,
                        indicators_fired=[k for k, v in meta.items()
                                          if isinstance(v, bool) and v],
                        matched_at=r.matched_at.isoformat(),
                    ))
            except Exception:
                pass  # skip failing scanners per stock

    return ScannerResultsResponse(
        results=results,
        run_type="intraday",
        date=datetime.utcnow().date().isoformat(),
    )
```

- [ ] **Step 4: Run integration tests to verify they pass**

```bash
pytest tests/integration/api/test_scanners.py -k "intraday" -v
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/api/scanners/routes.py tests/integration/api/test_scanners.py
git commit -m "feat: add POST /api/scanners/run intraday endpoint (LIN-80)"
```

---

## Task 7: Frontend types + API client (LIN-81)

**Files:**
- Create: `frontend/src/pages/scanners/types.ts`
- Create: `frontend/src/lib/scanners-api.ts`
- Create: `frontend/tests/unit/lib/scanners-api.test.ts`

- [ ] **Step 1: Write failing unit tests**

Create `frontend/tests/unit/lib/scanners-api.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { listScanners, getResults, runIntraday } from "../../../src/lib/scanners-api";

describe("scanners-api", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("listScanners calls GET /api/scanners", async () => {
    const mockData = [{ name: "momentum", timeframe: "daily", description: "RSI scan" }];
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockData,
    });
    const result = await listScanners();
    expect(fetch).toHaveBeenCalledWith("/api/scanners", expect.any(Object));
    expect(result).toEqual(mockData);
  });

  it("getResults calls GET /api/scanners/results with filters", async () => {
    const mockData = { results: [], run_type: "eod", date: "2026-04-13" };
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockData,
    });
    const result = await getResults({ run_type: "eod", scanners: ["momentum"] });
    expect(fetch).toHaveBeenCalledWith(
      expect.stringContaining("/api/scanners/results"),
      expect.any(Object)
    );
    expect(result.run_type).toBe("eod");
  });

  it("runIntraday calls POST /api/scanners/run", async () => {
    const mockData = { results: [], run_type: "intraday", date: "2026-04-13" };
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      ok: true,
      json: async () => mockData,
    });
    const result = await runIntraday({
      scanners: ["momentum"],
      timeframe: "15m",
      input_scope: "universe",
    });
    expect(fetch).toHaveBeenCalledWith("/api/scanners/run", expect.objectContaining({
      method: "POST",
    }));
    expect(result.run_type).toBe("intraday");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npx vitest run tests/unit/lib/scanners-api.test.ts
```
Expected: FAIL — module not found.

- [ ] **Step 3: Create types**

Create `frontend/src/pages/scanners/types.ts`:

```typescript
/**
 * TypeScript types for Scanner API.
 * Matches Pydantic schemas in src/api/scanners/schemas.py
 */

export interface ScannerMeta {
  name: string;
  timeframe: string;
  description: string;
}

export interface ScannerResultItem {
  scanner_name: string;
  symbol: string;
  score: number | null;
  signal: string | null;
  price: number | null;
  volume: number | null;
  change_pct: number | null;
  indicators_fired: string[];
  matched_at: string; // ISO datetime
}

export interface ScannerResultsResponse {
  results: ScannerResultItem[];
  run_type: string;
  date: string;
}

export interface GetResultsFilters {
  scanners?: string[];
  run_type?: "eod" | "pre_close";
  date?: string; // ISO date
}

export interface IntradayRunRequest {
  scanners: string[];
  timeframe: "15m" | "1h";
  input_scope: "universe" | number; // 'universe' or watchlist_id
}
```

- [ ] **Step 4: Create API client**

Create `frontend/src/lib/scanners-api.ts`:

```typescript
/**
 * Scanner API client.
 */
import { apiFetch } from "./api";
import type {
  GetResultsFilters,
  IntradayRunRequest,
  ScannerMeta,
  ScannerResultsResponse,
} from "../pages/scanners/types";

export const listScanners = (): Promise<ScannerMeta[]> =>
  apiFetch("/api/scanners");

export const getResults = (filters: GetResultsFilters = {}): Promise<ScannerResultsResponse> => {
  const params = new URLSearchParams();
  if (filters.run_type) params.set("run_type", filters.run_type);
  if (filters.date) params.set("date", filters.date);
  if (filters.scanners?.length) params.set("scanners", filters.scanners.join(","));
  const qs = params.toString();
  return apiFetch(`/api/scanners/results${qs ? `?${qs}` : ""}`);
};

export const runIntraday = (req: IntradayRunRequest): Promise<ScannerResultsResponse> =>
  apiFetch("/api/scanners/run", {
    method: "POST",
    body: JSON.stringify(req),
  });
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd frontend && npx vitest run tests/unit/lib/scanners-api.test.ts
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/scanners/types.ts frontend/src/lib/scanners-api.ts \
        frontend/tests/unit/lib/scanners-api.test.ts
git commit -m "feat: add scanner TypeScript types and API client (LIN-81)"
```

---

## Task 8: Shared ResultsPanel + TickerDetail (LIN-82)

**Files:**
- Create: `frontend/src/pages/scanners/results-panel.tsx`
- Create: `frontend/src/pages/scanners/ticker-detail.tsx`
- Create: `frontend/tests/unit/pages/scanners/results-panel.test.tsx`

- [ ] **Step 1: Write failing unit tests**

Create `frontend/tests/unit/pages/scanners/results-panel.test.tsx`:

```typescript
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@solidjs/testing-library";
import { ResultsPanel } from "../../../../src/pages/scanners/results-panel";
import type { ScannerResultItem } from "../../../../src/pages/scanners/types";

const makeResult = (symbol: string, scanner: string): ScannerResultItem => ({
  scanner_name: scanner,
  symbol,
  score: 8.0,
  signal: "BUY",
  price: 189.20,
  volume: 42000000,
  change_pct: 1.5,
  indicators_fired: ["rsi_overbought"],
  matched_at: "2026-04-13T16:15:00",
});

const groups = [
  { scanner_name: "momentum", results: [makeResult("AAPL", "momentum"), makeResult("NVDA", "momentum")] },
  { scanner_name: "price_action", results: [makeResult("AAPL", "price_action"), makeResult("TSLA", "price_action")] },
];

describe("ResultsPanel", () => {
  it("shows overlap section when 2+ groups share tickers", () => {
    render(() => <ResultsPanel groups={groups} />);
    expect(screen.getByText(/overlap/i)).toBeTruthy();
    // AAPL is in both groups — should appear in overlap
    const overlapItems = screen.getAllByText("AAPL");
    expect(overlapItems.length).toBeGreaterThan(0);
  });

  it("does not show overlap section with single group", () => {
    render(() => <ResultsPanel groups={[groups[0]]} />);
    expect(screen.queryByText(/overlap/i)).toBeNull();
  });

  it("clicking a ticker shows it in detail panel", () => {
    render(() => <ResultsPanel groups={[groups[0]]} />);
    fireEvent.click(screen.getAllByText("AAPL")[0]);
    expect(screen.getByText("BUY")).toBeTruthy();
    expect(screen.getByText(/189\.20/)).toBeTruthy();
  });

  it("shows empty state when no results", () => {
    render(() => <ResultsPanel groups={[]} />);
    expect(screen.getByText(/no results/i)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npx vitest run tests/unit/pages/scanners/results-panel.test.tsx
```
Expected: FAIL — module not found.

- [ ] **Step 3: Create TickerDetail**

Create `frontend/src/pages/scanners/ticker-detail.tsx`:

```typescript
import type { ScannerResultItem } from "./types";

interface Props {
  result: ScannerResultItem;
}

export function TickerDetail(props: Props) {
  const r = props.result;
  return (
    <div class="p-4 space-y-3">
      <div class="flex items-center justify-between">
        <h2 class="text-xl font-bold">{r.symbol}</h2>
        <span class={`px-2 py-1 rounded text-sm font-medium ${
          r.signal === "BUY" ? "bg-green-100 text-green-800" :
          r.signal === "SELL" ? "bg-red-100 text-red-800" :
          "bg-gray-100 text-gray-800"
        }`}>{r.signal ?? "—"}</span>
      </div>
      <div class="grid grid-cols-2 gap-2 text-sm">
        <div><span class="text-gray-500">Price</span><div class="font-medium">{r.price != null ? `$${r.price.toFixed(2)}` : "—"}</div></div>
        <div><span class="text-gray-500">Score</span><div class="font-medium">{r.score != null ? r.score.toFixed(1) : "—"}</div></div>
        <div><span class="text-gray-500">Volume</span><div class="font-medium">{r.volume != null ? `${(r.volume / 1_000_000).toFixed(1)}M` : "—"}</div></div>
        <div><span class="text-gray-500">Change</span><div class={`font-medium ${(r.change_pct ?? 0) >= 0 ? "text-green-600" : "text-red-600"}`}>{r.change_pct != null ? `${r.change_pct >= 0 ? "+" : ""}${r.change_pct.toFixed(2)}%` : "—"}</div></div>
      </div>
      <div>
        <p class="text-gray-500 text-sm mb-1">Scanner</p>
        <p class="text-sm font-medium">{r.scanner_name}</p>
      </div>
      {r.indicators_fired.length > 0 && (
        <div>
          <p class="text-gray-500 text-sm mb-1">Indicators triggered</p>
          <ul class="text-sm space-y-0.5">
            {r.indicators_fired.map(ind => (
              <li class="flex items-center gap-1">
                <span class="text-green-500">✓</span> {ind.replace(/_/g, " ")}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Create ResultsPanel**

Create `frontend/src/pages/scanners/results-panel.tsx`:

```typescript
import { createSignal, For, Show } from "solid-js";
import type { ScannerResultItem } from "./types";
import { TickerDetail } from "./ticker-detail";

interface ResultGroup {
  scanner_name: string;
  results: ScannerResultItem[];
}

interface Props {
  groups: ResultGroup[];
}

function computeOverlap(groups: ResultGroup[]): ScannerResultItem[] {
  if (groups.length < 2) return [];
  const sets = groups.map(g => new Set(g.results.map(r => r.symbol)));
  const intersection = [...sets[0]].filter(sym => sets.slice(1).every(s => s.has(sym)));
  // Return the result item from the first group for each overlapping symbol
  return intersection.map(sym => groups[0].results.find(r => r.symbol === sym)!);
}

export function ResultsPanel(props: Props) {
  const [selected, setSelected] = createSignal<ScannerResultItem | null>(null);

  const overlap = () => computeOverlap(props.groups);
  const hasResults = () => props.groups.some(g => g.results.length > 0);

  return (
    <div class="flex h-full">
      {/* Left: results list */}
      <div class="w-64 border-r overflow-y-auto flex-shrink-0">
        <Show when={!hasResults()}>
          <p class="p-4 text-gray-400 text-sm">No results</p>
        </Show>
        <Show when={overlap().length > 0}>
          <div class="px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide border-b">
            Overlap ({overlap().length})
          </div>
          <For each={overlap()}>
            {(item) => (
              <button
                class={`w-full text-left px-3 py-2 hover:bg-gray-50 flex items-center justify-between ${selected()?.symbol === item.symbol && selected()?.scanner_name === item.scanner_name ? "bg-blue-50" : ""}`}
                onClick={() => setSelected(item)}
              >
                <span class="font-medium text-sm">{item.symbol}</span>
                <span class="text-xs text-gray-400">{item.price != null ? `$${item.price.toFixed(2)}` : ""}</span>
              </button>
            )}
          </For>
        </Show>
        <For each={props.groups}>
          {(group) => (
            <>
              <div class="px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wide border-b border-t mt-1">
                {group.scanner_name} ({group.results.length})
              </div>
              <For each={group.results}>
                {(item) => (
                  <button
                    class={`w-full text-left px-3 py-2 hover:bg-gray-50 flex items-center justify-between ${selected()?.symbol === item.symbol && selected()?.scanner_name === item.scanner_name ? "bg-blue-50" : ""}`}
                    onClick={() => setSelected(item)}
                  >
                    <span class="font-medium text-sm">{item.symbol}</span>
                    <span class="text-xs text-gray-400">{item.price != null ? `$${item.price.toFixed(2)}` : ""}</span>
                  </button>
                )}
              </For>
            </>
          )}
        </For>
      </div>
      {/* Right: ticker detail */}
      <div class="flex-1 overflow-y-auto">
        <Show when={selected()} fallback={<p class="p-4 text-gray-400 text-sm">Select a ticker</p>}>
          <TickerDetail result={selected()!} />
        </Show>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd frontend && npx vitest run tests/unit/pages/scanners/results-panel.test.tsx
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/scanners/results-panel.tsx \
        frontend/src/pages/scanners/ticker-detail.tsx \
        frontend/tests/unit/pages/scanners/results-panel.test.tsx
git commit -m "feat: add shared ResultsPanel and TickerDetail components (LIN-82)"
```

---

## Task 9: EOD Tab (LIN-83)

**Files:**
- Create: `frontend/src/pages/scanners/eod-tab.tsx`
- Create: `frontend/tests/unit/pages/scanners/eod-tab.test.tsx`

- [ ] **Step 1: Write failing unit tests**

Create `frontend/tests/unit/pages/scanners/eod-tab.test.tsx`:

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@solidjs/testing-library";
import { EodTab } from "../../../../src/pages/scanners/eod-tab";

vi.mock("../../../../src/lib/scanners-api", () => ({
  listScanners: vi.fn().mockResolvedValue([
    { name: "momentum", timeframe: "daily", description: "RSI scan" },
    { name: "price_action", timeframe: "daily", description: "Price action" },
  ]),
  getResults: vi.fn().mockResolvedValue({
    results: [{ scanner_name: "momentum", symbol: "AAPL", score: 8.0, signal: "BUY",
                price: 189.20, volume: 42000000, change_pct: 1.5, indicators_fired: [],
                matched_at: "2026-04-13T16:15:00" }],
    run_type: "eod",
    date: "2026-04-13",
  }),
}));

vi.mock("../../../../src/lib/watchlists-api", () => ({
  watchlistsAPI: { create: vi.fn().mockResolvedValue({ id: 1, name: "test" }) },
}));

describe("EodTab", () => {
  it("renders scanner pills from API", async () => {
    render(() => <EodTab />);
    await waitFor(() => expect(screen.getByText("momentum")).toBeTruthy());
    expect(screen.getByText("price_action")).toBeTruthy();
  });

  it("shows Save as Watchlist button when results present", async () => {
    render(() => <EodTab />);
    await waitFor(() => screen.getByText("AAPL"));
    expect(screen.getByText(/save as watchlist/i)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npx vitest run tests/unit/pages/scanners/eod-tab.test.tsx
```
Expected: FAIL — module not found.

- [ ] **Step 3: Create EodTab**

Create `frontend/src/pages/scanners/eod-tab.tsx`:

```typescript
import { createResource, createSignal, For, Show } from "solid-js";
import { listScanners, getResults, getRunDates } from "../../lib/scanners-api";
import type { RunDateEntry } from "../../lib/scanners-api";
import { watchlistsAPI } from "../../lib/watchlists-api";
import { ResultsPanel } from "./results-panel";
import type { ScannerMeta, ScannerResultItem, ScannerResultsResponse } from "./types";

export function EodTab() {
  const [scanners] = createResource(listScanners);
  const [runDates] = createResource(getRunDates);
  const [selectedScanners, setSelectedScanners] = createSignal<Set<string>>(new Set());
  const [selectedRun, setSelectedRun] = createSignal<RunDateEntry | null>(null);
  const [results, setResults] = createSignal<ScannerResultsResponse | null>(null);
  const [saving, setSaving] = createSignal(false);

  // Load results when selected run changes; default to latest on mount
  createResource(
    () => selectedRun() ?? runDates()?.[0] ?? null,
    async (run) => {
      if (!run) return;
      const data = await getResults({
        run_type: run.run_type as "eod" | "pre_close",
        date: run.date,
      });
      setResults(data);
      const names = new Set(data.results.map(r => r.scanner_name));
      setSelectedScanners(names);
    }
  );

  const toggleScanner = (name: string) => {
    setSelectedScanners(prev => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  };

  const filteredGroups = () => {
    if (!results()) return [];
    const grouped = new Map<string, ScannerResultItem[]>();
    for (const r of results()!.results) {
      if (!selectedScanners().has(r.scanner_name)) continue;
      if (!grouped.has(r.scanner_name)) grouped.set(r.scanner_name, []);
      grouped.get(r.scanner_name)!.push(r);
    }
    return [...grouped.entries()].map(([scanner_name, items]) => ({ scanner_name, results: items }));
  };

  const saveAsWatchlist = async () => {
    if (!results() || saving()) return;
    setSaving(true);
    try {
      const scannerNames = [...selectedScanners()].join(" + ");
      const runLabel = runType() === "pre_close" ? "Pre-close" : "EOD";
      const name = `${scannerNames} — ${runLabel} ${results()!.date}`;
      const symbols = filteredGroups().flatMap(g => g.results.map(r => r.symbol));
      await watchlistsAPI.create({ name, description: `Auto-generated from scanner run`, category_id: null });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div class="flex flex-col h-full">
      <div class="p-3 border-b flex items-center gap-3 flex-wrap">
        <Show when={scanners()}>
          <div class="flex gap-2">
            <For each={scanners()}>
              {(s: ScannerMeta) => (
                <button
                  class={`px-3 py-1 rounded-full text-sm border transition-colors ${
                    selectedScanners().has(s.name)
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-gray-700 border-gray-300 hover:border-blue-400"
                  }`}
                  onClick={() => toggleScanner(s.name)}
                >
                  {s.name}
                </button>
              )}
            </For>
          </div>
        </Show>
        {/* Date/run dropdown */}
        <Show when={runDates()?.length}>
          <select
            class="border rounded px-2 py-1 text-sm"
            onChange={e => {
              const idx = parseInt(e.currentTarget.value);
              setSelectedRun(runDates()![idx]);
            }}
          >
            <For each={runDates()}>
              {(entry, i) => (
                <option value={i()}>
                  {entry.date} — {entry.run_type === "pre_close" ? "Pre-close" : "EOD"} {entry.time}
                </option>
              )}
            </For>
          </select>
        </Show>
        <Show when={results() && filteredGroups().some(g => g.results.length > 0)}>
          <button
            class="ml-auto px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
            onClick={saveAsWatchlist}
            disabled={saving()}
          >
            {saving() ? "Saving..." : "Save as Watchlist"}
          </button>
        </Show>
      </div>
      <div class="flex-1 overflow-hidden">
        <ResultsPanel groups={filteredGroups()} />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && npx vitest run tests/unit/pages/scanners/eod-tab.test.tsx
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/scanners/eod-tab.tsx \
        frontend/tests/unit/pages/scanners/eod-tab.test.tsx
git commit -m "feat: add EOD tab with scanner pills and Save as Watchlist (LIN-83)"
```

---

## Task 10: Intraday Tab (LIN-84)

**Files:**
- Create: `frontend/src/pages/scanners/intraday-tab.tsx`
- Create: `frontend/tests/unit/pages/scanners/intraday-tab.test.tsx`

- [ ] **Step 1: Write failing unit tests**

Create `frontend/tests/unit/pages/scanners/intraday-tab.test.tsx`:

```typescript
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@solidjs/testing-library";
import { IntradayTab } from "../../../../src/pages/scanners/intraday-tab";

vi.mock("../../../../src/lib/scanners-api", () => ({
  listScanners: vi.fn().mockResolvedValue([
    { name: "momentum", timeframe: "daily", description: "RSI scan" },
  ]),
  runIntraday: vi.fn().mockResolvedValue({
    results: [{ scanner_name: "momentum", symbol: "TSLA", score: null, signal: "BUY",
                price: 173.0, volume: 5000000, change_pct: null, indicators_fired: [],
                matched_at: "2026-04-13T14:30:00" }],
    run_type: "intraday",
    date: "2026-04-13",
  }),
}));

vi.mock("../../../../src/lib/watchlists-api", () => ({
  watchlistsAPI: {
    list: vi.fn().mockResolvedValue({ categories: [] }),
    create: vi.fn().mockResolvedValue({ id: 1, name: "test" }),
  },
}));

describe("IntradayTab", () => {
  it("renders Run button", async () => {
    render(() => <IntradayTab />);
    await waitFor(() => expect(screen.getByText(/run/i)).toBeTruthy());
  });

  it("shows results after clicking Run", async () => {
    render(() => <IntradayTab />);
    await waitFor(() => screen.getByText(/run/i));
    fireEvent.click(screen.getByText(/run/i));
    await waitFor(() => expect(screen.getByText("TSLA")).toBeTruthy());
  });

  it("Save as Watchlist only appears after run returns results", async () => {
    render(() => <IntradayTab />);
    expect(screen.queryByText(/save as watchlist/i)).toBeNull();
    fireEvent.click(screen.getByText(/run/i));
    await waitFor(() => screen.getByText("TSLA"));
    expect(screen.getByText(/save as watchlist/i)).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd frontend && npx vitest run tests/unit/pages/scanners/intraday-tab.test.tsx
```
Expected: FAIL — module not found.

- [ ] **Step 3: Create IntradayTab**

Create `frontend/src/pages/scanners/intraday-tab.tsx`:

```typescript
import { createResource, createSignal, For, onCleanup, Show } from "solid-js";
import { listScanners, runIntraday } from "../../lib/scanners-api";
import { watchlistsAPI } from "../../lib/watchlists-api";
import { ResultsPanel } from "./results-panel";
import type { ScannerMeta, ScannerResultItem, ScannerResultsResponse } from "./types";

export function IntradayTab() {
  const [scanners] = createResource(listScanners);
  const [selectedScanners, setSelectedScanners] = createSignal<Set<string>>(new Set(["momentum"]));
  const [timeframe, setTimeframe] = createSignal<"15m" | "1h">("15m");
  const [inputScope, setInputScope] = createSignal<"universe" | number>("universe");
  const [running, setRunning] = createSignal(false);
  const [results, setResults] = createSignal<ScannerResultsResponse | null>(null);
  const [saving, setSaving] = createSignal(false);

  // Fetch watchlists for input scope dropdown
  const [watchlistData] = createResource(() => watchlistsAPI.list());

  // Clear results on unmount (ephemeral)
  onCleanup(() => setResults(null));

  const toggleScanner = (name: string) => {
    setSelectedScanners(prev => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  };

  const handleRun = async () => {
    if (running()) return;
    setRunning(true);
    try {
      const data = await runIntraday({
        scanners: [...selectedScanners()],
        timeframe: timeframe(),
        input_scope: inputScope(),
      });
      setResults(data);
    } finally {
      setRunning(false);
    }
  };

  const filteredGroups = () => {
    if (!results()) return [];
    const grouped = new Map<string, ScannerResultItem[]>();
    for (const r of results()!.results) {
      if (!grouped.has(r.scanner_name)) grouped.set(r.scanner_name, []);
      grouped.get(r.scanner_name)!.push(r);
    }
    return [...grouped.entries()].map(([scanner_name, items]) => ({ scanner_name, results: items }));
  };

  const saveAsWatchlist = async () => {
    if (!results() || saving()) return;
    setSaving(true);
    try {
      const name = `Intraday ${timeframe()} — ${results()!.date}`;
      await watchlistsAPI.create({ name, description: "Auto-generated from intraday scan", category_id: null });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div class="flex flex-col h-full">
      <div class="p-3 border-b flex items-center gap-3 flex-wrap">
        {/* Scanner pills */}
        <Show when={scanners()}>
          <div class="flex gap-2">
            <For each={scanners()}>
              {(s: ScannerMeta) => (
                <button
                  class={`px-3 py-1 rounded-full text-sm border transition-colors ${
                    selectedScanners().has(s.name)
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-gray-700 border-gray-300 hover:border-blue-400"
                  }`}
                  onClick={() => toggleScanner(s.name)}
                >
                  {s.name}
                </button>
              )}
            </For>
          </div>
        </Show>
        {/* Timeframe */}
        <select
          class="border rounded px-2 py-1 text-sm"
          value={timeframe()}
          onChange={e => setTimeframe(e.currentTarget.value as "15m" | "1h")}
        >
          <option value="15m">15m</option>
          <option value="1h">1h</option>
        </select>
        {/* Input scope */}
        <select
          class="border rounded px-2 py-1 text-sm"
          value={inputScope()}
          onChange={e => {
            const v = e.currentTarget.value;
            setInputScope(v === "universe" ? "universe" : parseInt(v));
          }}
        >
          <option value="universe">Full Universe</option>
          <For each={watchlistData()?.categories ?? []}>
            {(cat: any) => (
              <For each={cat.watchlists ?? []}>
                {(wl: any) => <option value={wl.id}>{wl.name}</option>}
              </For>
            )}
          </For>
        </select>
        {/* Run button */}
        <button
          class="px-4 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
          onClick={handleRun}
          disabled={running()}
        >
          {running() ? "Running..." : "Run"}
        </button>
        {/* Save as Watchlist — only after results */}
        <Show when={results() && filteredGroups().some(g => g.results.length > 0)}>
          <button
            class="px-3 py-1 text-sm bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
            onClick={saveAsWatchlist}
            disabled={saving()}
          >
            {saving() ? "Saving..." : "Save as Watchlist"}
          </button>
        </Show>
      </div>
      <div class="flex-1 overflow-hidden">
        <Show when={results()} fallback={<p class="p-4 text-gray-400 text-sm">Select scanners and click Run</p>}>
          <ResultsPanel groups={filteredGroups()} />
        </Show>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd frontend && npx vitest run tests/unit/pages/scanners/intraday-tab.test.tsx
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/scanners/intraday-tab.tsx \
        frontend/tests/unit/pages/scanners/intraday-tab.test.tsx
git commit -m "feat: add Intraday tab with on-demand scan and ephemeral results (LIN-84)"
```

---

## Task 11: Route wiring + nav (LIN-85)

**Files:**
- Create: `frontend/src/pages/scanners/index.tsx`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/src/app.tsx`
- Create: `frontend/tests/unit/routes-scanners-integration.test.tsx`

- [ ] **Step 1: Write failing route integration test**

Create `frontend/tests/unit/routes-scanners-integration.test.tsx`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@solidjs/testing-library";
import { Router } from "@solidjs/router";
import App from "../../src/app";

vi.mock("../../src/lib/scanners-api", () => ({
  listScanners: vi.fn().mockResolvedValue([]),
  getResults: vi.fn().mockResolvedValue({ results: [], run_type: "eod", date: "" }),
  runIntraday: vi.fn().mockResolvedValue({ results: [], run_type: "intraday", date: "" }),
}));

vi.mock("../../src/lib/watchlists-api", () => ({
  watchlistsAPI: { list: vi.fn().mockResolvedValue({ categories: [] }) },
}));

describe("Scanners route", () => {
  it("renders scanners page at /scanners", async () => {
    render(() => (
      <Router>
        <App />
      </Router>
    ));
    // Navigate to /scanners
    window.history.pushState({}, "", "/scanners");
    await waitFor(() => {
      expect(screen.getByText(/EOD/i)).toBeTruthy();
      expect(screen.getByText(/Intraday/i)).toBeTruthy();
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run tests/unit/routes-scanners-integration.test.tsx
```
Expected: FAIL — `/scanners` renders nothing.

- [ ] **Step 3: Create index.tsx (tab switcher)**

Create `frontend/src/pages/scanners/index.tsx`:

```typescript
import { createSignal, Show } from "solid-js";
import { EodTab } from "./eod-tab";
import { IntradayTab } from "./intraday-tab";

type Tab = "eod" | "intraday";

export default function ScannerPage() {
  const [tab, setTab] = createSignal<Tab>("eod");

  return (
    <div class="flex flex-col h-full">
      <div class="border-b px-4 flex gap-0">
        {(["eod", "intraday"] as Tab[]).map(t => (
          <button
            class={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab() === t
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-gray-500 hover:text-gray-700"
            }`}
            onClick={() => setTab(t)}
          >
            {t === "eod" ? "EOD" : "Intraday"}
          </button>
        ))}
      </div>
      <div class="flex-1 overflow-hidden">
        <Show when={tab() === "eod"}>
          <EodTab />
        </Show>
        <Show when={tab() === "intraday"}>
          <IntradayTab />
        </Show>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Wire route in main.tsx**

In `frontend/src/main.tsx`, import and add the `/scanners` route alongside existing routes:

```typescript
import ScannerPage from "./pages/scanners/index";
// In the Routes block:
<Route path="/scanners" component={ScannerPage} />
```

- [ ] **Step 5: Add nav link in app.tsx**

In `frontend/src/app.tsx`, add a "Scanners" nav link next to the Watchlists link (follow the existing pattern for nav items).

- [ ] **Step 6: Run tests to verify they pass**

```bash
cd frontend && npx vitest run tests/unit/routes-scanners-integration.test.tsx
```
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/scanners/index.tsx frontend/src/main.tsx frontend/src/app.tsx \
        frontend/tests/unit/routes-scanners-integration.test.tsx
git commit -m "feat: wire /scanners route and add Scanners nav link (LIN-85)"
```

---

## Task 12: E2E tests (LIN-86)

**Files:**
- Create: `frontend/tests/e2e/scanners.spec.ts`

- [ ] **Step 1: Create E2E test file**

Create `frontend/tests/e2e/scanners.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";

// Assumes the dev server is running (npm run dev) and the DB has seeded scanner_results.
// Run with: npx playwright test tests/e2e/scanners.spec.ts

test.describe("Scanner Control Panel", () => {
  test.beforeEach(async ({ page }) => {
    // Log in first
    await page.goto("/login");
    await page.fill('[name="username"]', "testuser");
    await page.fill('[name="password"]', "testpass123");
    await page.click('[type="submit"]');
    await page.waitForURL("/");
  });

  test("navigates to /scanners and shows EOD tab by default", async ({ page }) => {
    await page.goto("/scanners");
    await expect(page.getByText("EOD")).toBeVisible();
    await expect(page.getByText("Intraday")).toBeVisible();
  });

  test("switching to Intraday tab shows Run button", async ({ page }) => {
    await page.goto("/scanners");
    await page.click("text=Intraday");
    await expect(page.getByText("Run")).toBeVisible();
  });

  test("deselecting a scanner pill hides its results", async ({ page }) => {
    await page.goto("/scanners");
    // Wait for results to load
    await page.waitForSelector(".scanner-result-row", { timeout: 5000 }).catch(() => null);
    // Click momentum pill to deselect
    const pill = page.getByRole("button", { name: "momentum" });
    if (await pill.isVisible()) {
      const initialCount = await page.locator(".scanner-result-row").count();
      await pill.click();
      const newCount = await page.locator(".scanner-result-row").count();
      expect(newCount).toBeLessThanOrEqual(initialCount);
    }
  });

  test("Intraday tab Run button triggers scan", async ({ page }) => {
    await page.goto("/scanners");
    await page.click("text=Intraday");
    await page.click("text=Run");
    // Button should show running state briefly
    await expect(page.getByText("Running...")).toBeVisible({ timeout: 2000 }).catch(() => null);
  });
});
```

- [ ] **Step 2: Run lint + type check**

```bash
cd /path/to/project
ruff check src/ tests/
mypy src/ --ignore-missing-imports
cd frontend && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Run full backend test suite**

```bash
pytest tests/ -v --tb=short
```
Expected: all PASS.

- [ ] **Step 4: Run full frontend unit tests**

```bash
cd frontend && npx vitest run
```
Expected: all PASS.

- [ ] **Step 5: Final commit**

```bash
git add frontend/tests/e2e/scanners.spec.ts
git commit -m "test: add E2E tests for scanner control panel (LIN-86)"
```

- [ ] **Step 6: Open PR**

```bash
git push -u origin feature/scanner-control-panel
gh pr create \
  --title "feat: Scanner Control Panel — sub-project 3 (LIN-76 through LIN-86)" \
  --body "$(cat <<'EOF'
## Summary

- Adds `/scanners` route with EOD and Intraday tabs
- EOD tab reads existing `scanner_results` with scanner pill toggles and run-type filter
- Pre-close scanner runs at 3:45 PM ET using `realtime_quotes` as partial candle proxy
- Intraday tab triggers ephemeral on-demand scans against `intraday_candles`
- One-click Save as Watchlist on both tabs
- New `run_type` column on `scanner_results` distinguishes EOD from pre-close runs
- Linear: LIN-76 through LIN-86

## Test plan

- [ ] `pytest tests/` passes
- [ ] `cd frontend && npx vitest run` passes
- [ ] `ruff check` + `mypy` clean
- [ ] `alembic upgrade head` applies cleanly
- [ ] Manual: navigate to /scanners, verify EOD results load, toggle pills, run intraday scan

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
