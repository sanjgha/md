# Charts Module Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a multi-timeframe chart panel for the watchlist right pane using lightweight-charts, reading candle data from PostgreSQL with independent split-panel support.

**Architecture:** Two-layer backend (FastAPI routes → SQLAlchemy service → PostgreSQL queries), SolidJS frontend with lightweight-charts canvas rendering. Per-panel independent state management via Solid signals.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, PostgreSQL 16, SolidJS, lightweight-charts, Vitest, pytest.

---

## File Structure Overview

```
src/api/stocks/
├── __init__.py           # Package init
├── routes.py             # GET /{symbol}/candles endpoint
├── schemas.py            # CandleResponse Pydantic schema
└── service.py            # StockService with get_candles()

frontend/src/pages/watchlists/
├── dashboard.tsx         # Pass selectedSymbol to ChartPane (MODIFY)
├── chart-pane.tsx        # Right pane shell, owns panelCount
└── chart-panel.tsx       # Single chart unit with controls

frontend/src/lib/
├── stocks-api.ts         # getCandles() API client
└── chart-utils.ts        # Timeframe → date range helpers

tests/unit/test_stocks_service.py        # Unit tests
tests/integration/test_stocks_routes.py  # Integration tests
frontend/src/lib/stocks-api.test.ts      # API client tests
frontend/src/pages/watchlists/chart-panel.test.tsx  # Component tests

alembic/versions/xxx_add_intraday_res_index.py  # Migration
```

---

## Part 1: Backend — Database Migration

### Task 1: Create migration for intraday_candles composite index

**Files:**
- Create: `alembic/versions/001_add_intraday_res_index.py`

- [ ] **Step 1: Generate Alembic migration**

Run: `alembic revision -m "add_intraday_res_index"`

Expected: New migration file created in `alembic/versions/`

- [ ] **Step 2: Edit the migration file**

Open the generated migration file and replace the `upgrade()` and `downgrade()` functions:

```python
from alembic import op
import sqlalchemy as sa


def upgrade():
    """Add composite index on intraday_candles for hot query path."""
    op.create_index(
        'ix_intraday_candles_stock_res_ts',
        'intraday_candles',
        ['stock_id', 'resolution', 'timestamp']
    )


def downgrade():
    """Remove the composite index."""
    op.drop_index('ix_intraday_candles_stock_res_ts', table_name='intraday_candles')
```

- [ ] **Step 3: Verify migration syntax**

Run: `alembic check`

Expected: No SQL syntax errors

- [ ] **Step 4: Commit**

```bash
git add alembic/versions/
git commit -m "feat: add intraday_candles composite index for chart queries"
```

---

## Part 2: Backend — Pydantic Schemas

### Task 2: Create CandleResponse schema

**Files:**
- Create: `src/api/stocks/schemas.py`

- [ ] **Step 1: Create schemas module with CandleResponse**

Create `src/api/stocks/schemas.py`:

```python
"""Pydantic schemas for stocks API."""

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class CandleResponse(BaseModel):
    """Single OHLCV candle response."""

    time: datetime = Field(..., description="Candle timestamp (datetime for intraday, date for daily)")
    open: float = Field(..., gt=0, description="Opening price")
    high: float = Field(..., gt=0, description="Highest price")
    low: float = Field(..., gt=0, description="Lowest price")
    close: float = Field(..., gt=0, description="Closing price")
    volume: int = Field(..., ge=0, description="Trading volume")

    class Config:
        """Pydantic config."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class CandlesResponse(BaseModel):
    """Response wrapper for candle array."""

    candles: List[CandleResponse] = Field(default_factory=list, description="Array of OHLCV candles")
```

- [ ] **Step 2: Write validation test**

Create `tests/unit/test_stocks_schemas.py`:

```python
"""Unit tests for stocks schemas."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from src.api.stocks.schemas import CandleResponse, CandlesResponse


def test_candle_response_valid():
    """Test valid candle response."""
    candle_data = {
        "time": "2026-04-16T09:30:00",
        "open": 180.20,
        "high": 188.40,
        "low": 179.80,
        "close": 186.59,
        "volume": 52300000,
    }
    candle = CandleResponse(**candle_data)
    assert candle.open == 180.20
    assert candle.close == 186.59


def test_candle_response_validation_fails_on_negative_price():
    """Test that negative prices are rejected."""
    with pytest.raises(ValidationError):
        CandleResponse(
            time="2026-04-16T09:30:00",
            open=-10.0,
            high=188.40,
            low=179.80,
            close=186.59,
            volume=52300000,
        )


def test_candles_response_empty_array():
    """Test empty candles response."""
    response = CandlesResponse()
    assert response.candles == []
```

- [ ] **Step 3: Run test to verify it passes**

Run: `pytest tests/unit/test_stocks_schemas.py -v`

Expected: PASS (all 3 tests)

- [ ] **Step 4: Commit**

```bash
git add src/api/stocks/schemas.py tests/unit/test_stocks_schemas.py
git commit -m "feat: add CandleResponse Pydantic schema with validation"
```

---

## Part 3: Backend — Service Layer

### Task 3: Create StockService with get_candles()

**Files:**
- Create: `src/api/stocks/service.py`
- Test: `tests/unit/test_stocks_service.py`

- [ ] **Step 1: Write test for resolution routing**

Create `tests/unit/test_stocks_service.py`:

```python
"""Unit tests for StockService."""

import pytest
from datetime import date, datetime
from sqlalchemy.orm import Session

from src.api.stocks.service import StockService
from src.db.models import DailyCandle, IntradayCandle, Stock


def test_get_candles_5m_routes_to_intraday(db_session: Session):
    """Test that 5m resolution queries intraday_candles."""
    # Create test stock
    stock = Stock(symbol="TEST", name="Test Stock")
    db_session.add(stock)
    db_session.flush()

    # Create test intraday candle
    candle = IntradayCandle(
        stock_id=stock.id,
        resolution="5m",
        timestamp=datetime(2026, 4, 16, 9, 30),
        open=100.0,
        high=105.0,
        low=99.0,
        close=104.0,
        volume=1000,
    )
    db_session.add(candle)
    db_session.commit()

    service = StockService(db_session)
    candles = service.get_candles(
        symbol="TEST",
        resolution="5m",
        start_date=datetime(2026, 4, 16),
        end_date=datetime(2026, 4, 17),
    )

    assert len(candles) == 1
    assert candles[0].open == 100.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_stocks_service.py::test_get_candles_5m_routes_to_intraday -v`

Expected: FAIL with "StockService not defined"

- [ ] **Step 3: Implement StockService class**

Create `src/api/stocks/service.py`:

```python
"""Service layer for stocks API."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.stocks.schemas import CandleResponse
from src.db.models import DailyCandle, IntradayCandle, Stock


class StockService:
    """Service layer for stock candle data."""

    # Resolution to max range mapping (days)
    MAX_RANGES = {
        "5m": 7,
        "15m": 30,
        "1h": 90,
        "D": 730,  # 2 years
    }

    # Valid resolutions
    VALID_RESOLUTIONS = {"5m", "15m", "1h", "D"}

    def __init__(self, db_session: Session):
        """Initialize service with database session.

        Args:
            db_session: SQLAlchemy Session
        """
        self.db_session = db_session

    def get_candles(
        self,
        symbol: str,
        resolution: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[CandleResponse]:
        """Fetch OHLCV candles for a symbol.

        Args:
            symbol: Stock ticker symbol
            resolution: Timeframe (5m, 15m, 1h, D)
            start_date: Start of query range
            end_date: End of query range

        Returns:
            List of candle responses

        Raises:
            ValueError: If resolution is invalid or date range exceeds max
        """
        # Validate resolution
        if resolution not in self.VALID_RESOLUTIONS:
            raise ValueError(f"Invalid resolution: {resolution}")

        # Validate max range
        max_range_days = self.MAX_RANGES[resolution]
        actual_range = (end_date - start_date).days
        if actual_range > max_range_days:
            raise ValueError(
                f"Date range {actual_range} days exceeds max {max_range_days} for resolution {resolution}"
            )

        # Resolve stock_id
        stock = self.db_session.execute(
            select(Stock).where(Stock.symbol == symbol.upper())
        ).scalar_one_or_none()

        if not stock:
            raise ValueError(f"Stock not found: {symbol}")

        # Route to appropriate table
        if resolution in {"5m", "15m", "1h"}:
            return self._get_intraday_candles(stock.id, resolution, start_date, end_date)
        else:  # resolution == "D"
            return self._get_daily_candles(stock.id, start_date, end_date)

    def _get_intraday_candles(
        self,
        stock_id: int,
        resolution: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[CandleResponse]:
        """Fetch intraday candles."""
        stmt = (
            select(IntradayCandle)
            .where(
                IntradayCandle.stock_id == stock_id,
                IntradayCandle.resolution == resolution,
                IntradayCandle.timestamp >= start_date,
                IntradayCandle.timestamp <= end_date,
            )
            .order_by(IntradayCandle.timestamp.asc())
        )

        results = self.db_session.execute(stmt).scalars().all()

        return [
            CandleResponse(
                time=c.timestamp,
                open=float(c.open),
                high=float(c.high),
                low=float(c.low),
                close=float(c.close),
                volume=c.volume,
            )
            for c in results
        ]

    def _get_daily_candles(
        self,
        stock_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> List[CandleResponse]:
        """Fetch daily candles."""
        stmt = (
            select(DailyCandle)
            .where(
                DailyCandle.stock_id == stock_id,
                DailyCandle.timestamp >= start_date,
                DailyCandle.timestamp <= end_date,
            )
            .order_by(DailyCandle.timestamp.asc())
        )

        results = self.db_session.execute(stmt).scalars().all()

        return [
            CandleResponse(
                time=c.timestamp,
                open=float(c.open),
                high=float(c.high),
                low=float(c.low),
                close=float(c.close),
                volume=c.volume,
            )
            for c in results
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_stocks_service.py::test_get_candles_5m_routes_to_intraday -v`

Expected: PASS

- [ ] **Step 5: Write additional validation tests**

Add to `tests/unit/test_stocks_service.py`:

```python
def test_get_candles_invalid_resolution_raises_value_error(db_session: Session):
    """Test that invalid resolution raises ValueError."""
    service = StockService(db_session)

    with pytest.raises(ValueError, match="Invalid resolution"):
        service.get_candles(
            symbol="TEST",
            resolution="invalid",
            start_date=datetime(2026, 4, 16),
            end_date=datetime(2026, 4, 17),
        )


def test_get_candles_exceeds_max_range_raises_value_error(db_session: Session):
    """Test that exceeding max range raises ValueError."""
    service = StockService(db_session)

    with pytest.raises(ValueError, match="exceeds max"):
        service.get_candles(
            symbol="TEST",
            resolution="5m",
            start_date=datetime(2026, 4, 1),
            end_date=datetime(2026, 4, 20),  # 19 days > 7 day max
        )


def test_get_candles_daily_resolution(db_session: Session):
    """Test that D resolution queries daily_candles."""
    stock = Stock(symbol="TEST", name="Test Stock")
    db_session.add(stock)
    db_session.flush()

    candle = DailyCandle(
        stock_id=stock.id,
        timestamp=date(2026, 4, 16),
        open=100.0,
        high=105.0,
        low=99.0,
        close=104.0,
        volume=1000,
    )
    db_session.add(candle)
    db_session.commit()

    service = StockService(db_session)
    candles = service.get_candles(
        symbol="TEST",
        resolution="D",
        start_date=datetime(2026, 4, 16),
        end_date=datetime(2026, 4, 17),
    )

    assert len(candles) == 1
    assert candles[0].open == 100.0


def test_get_candles_unknown_symbol_raises_value_error(db_session: Session):
    """Test that unknown symbol raises ValueError."""
    service = StockService(db_session)

    with pytest.raises(ValueError, match="Stock not found"):
        service.get_candles(
            symbol="UNKNOWN",
            resolution="D",
            start_date=datetime(2026, 4, 16),
            end_date=datetime(2026, 4, 17),
        )


def test_get_candles_timezone_edge_case(db_session: Session):
    """Test that date filtering works correctly across timezone boundaries."""
    stock = Stock(symbol="TEST", name="Test Stock")
    db_session.add(stock)
    db_session.flush()

    # Create candle at midnight UTC (edge case)
    candle = IntradayCandle(
        stock_id=stock.id,
        resolution="5m",
        timestamp=datetime(2026, 4, 16, 0, 0),  # Midnight UTC
        open=100.0,
        high=105.0,
        low=99.0,
        close=104.0,
        volume=1000,
    )
    db_session.add(candle)
    db_session.commit()

    service = StockService(db_session)
    candles = service.get_candles(
        symbol="TEST",
        resolution="5m",
        start_date=datetime(2026, 4, 15),  # Day before
        end_date=datetime(2026, 4, 17),    # Day after
    )

    assert len(candles) == 1
    assert candles[0].open == 100.0
```

- [ ] **Step 6: Run all service tests**

Run: `pytest tests/unit/test_stocks_service.py -v`

Expected: PASS (all 6 tests)

- [ ] **Step 7: Commit**

```bash
git add src/api/stocks/service.py tests/unit/test_stocks_service.py
git commit -m "feat: implement StockService.get_candles with validation and routing"
```

---

## Part 4: Backend — API Routes

### Task 4: Create GET /api/stocks/{symbol}/candles route

**Files:**
- Create: `src/api/stocks/routes.py`
- Create: `src/api/stocks/__init__.py`
- Modify: `src/api/main.py`

- [ ] **Step 1: Write integration test for happy path**

Create `tests/integration/test_stocks_routes.py`:

```python
"""Integration tests for stocks API routes."""

import pytest
from datetime import datetime, date

from src.db.models import DailyCandle, IntradayCandle, Stock


def test_get_candles_5m_happy_path(client, db_session):
    """Test successful 5m candle retrieval."""
    # Setup test data
    stock = Stock(symbol="AAPL", name="Apple Inc")
    db_session.add(stock)
    db_session.flush()

    candle = IntradayCandle(
        stock_id=stock.id,
        resolution="5m",
        timestamp=datetime(2026, 4, 16, 9, 30),
        open=180.20,
        high=188.40,
        low=179.80,
        close=186.59,
        volume=52300000,
    )
    db_session.add(candle)
    db_session.commit()

    response = client.get("/api/stocks/AAPL/candles?resolution=5m&from=2026-04-16&to=2026-04-17")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["open"] == 180.20
    assert data[0]["close"] == 186.59


def test_get_candles_unknown_symbol_returns_404(client):
    """Test that unknown symbol returns 404."""
    response = client.get("/api/stocks/UNKNOWN/candles?resolution=D&from=2026-04-16&to=2026-04-17")

    assert response.status_code == 404


def test_get_candles_invalid_resolution_returns_400(client):
    """Test that invalid resolution returns 400."""
    response = client.get("/api/stocks/AAPL/candles?resolution=invalid&from=2026-04-16&to=2026-04-17")

    assert response.status_code == 400


def test_get_candles_exceeds_max_range_returns_400(client):
    """Test that exceeding max range returns 400."""
    response = client.get("/api/stocks/AAPL/candles?resolution=5m&from=2026-04-01&to=2026-04-20")

    assert response.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_stocks_routes.py -v`

Expected: FAIL with "404 Not Found" (route doesn't exist yet)

- [ ] **Step 3: Create routes module**

Create `src/api/stocks/routes.py`:

```python
"""API routes for stocks candle data."""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.stocks.schemas import CandleResponse
from src.api.stocks.service import StockService

router = APIRouter()


@router.get("/{symbol}/candles", response_model=list[CandleResponse])
def get_candles(
    symbol: str,
    resolution: str = Query(..., regex="^(5m|15m|1h|D)$"),
    from_date: str = Query(..., alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: str = Query(..., alias="to", description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> list[CandleResponse]:
    """Get OHLCV candles for a symbol.

    Args:
        symbol: Stock ticker symbol
        resolution: Timeframe (5m, 15m, 1h, D)
        from_date: Start of date range
        to_date: End of date range
        db: Database session

    Returns:
        Array of OHLCV candles

    Raises:
        HTTPException: 404 if symbol not found, 400 for invalid params
    """
    service = StockService(db)

    try:
        start = datetime.fromisoformat(from_date)
        end = datetime.fromisoformat(to_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    try:
        candles = service.get_candles(
            symbol=symbol,
            resolution=resolution,
            start_date=start,
            end_date=end,
        )
        return candles
    except ValueError as e:
        # Check if it's a "stock not found" error
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        # Other validation errors
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 4: Create package init**

Create `src/api/stocks/__init__.py`:

```python
"""Stocks API package."""

from src.api.stocks.routes import router

__all__ = ["router"]
```

- [ ] **Step 5: Register router in main app**

Modify `src/api/main.py` — add the stocks router import and registration:

Find the existing router registrations and add:

```python
from src.api.stocks import router as stocks_router

# ... existing code ...

app.include_router(stocks_router, prefix="/api/stocks", tags=["stocks"])
```

- [ ] **Step 6: Run integration tests**

Run: `pytest tests/integration/test_stocks_routes.py -v`

Expected: PASS (all 4 tests)

- [ ] **Step 7: Commit**

```bash
git add src/api/stocks/ src/api/main.py tests/integration/test_stocks_routes.py
git commit -m "feat: add GET /api/stocks/{symbol}/candles endpoint with validation"
```

---

## Part 5: Frontend — API Client

### Task 5: Create stocks API client

**Files:**
- Create: `frontend/src/lib/stocks-api.ts`
- Test: `frontend/src/lib/stocks-api.test.ts`

- [ ] **Step 1: Write test for getCandles**

Create `frontend/src/lib/stocks-api.test.ts`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { stocksAPI } from "./stocks-api";

describe("stocksAPI", () => {
  it("getCandles constructs correct query params", () => {
    const fetchSpy = vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => [],
    } as Response);

    stocksAPI.getCandles("AAPL", "5m", "2026-04-16", "2026-04-17");

    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/stocks/AAPL/candles?resolution=5m&from=2026-04-16&to=2026-04-17"
    );
  });

  it("getCandles surfaces 404 errors", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue({
      ok: false,
      status: 404,
      statusText: "Not Found",
      json: async () => ({ detail: "Stock not found: AAPL" }),
    } as Response);

    await expect(stocksAPI.getCandles("AAPL", "D", "2026-04-16", "2026-04-17"))
      .rejects.toThrow("API error 404: Stock not found: AAPL");
  });

  it("getCandles returns parsed candle data", async () => {
    const mockCandles = [
      {
        time: "2026-04-16T09:30:00",
        open: 180.2,
        high: 188.4,
        low: 179.8,
        close: 186.59,
        volume: 52300000,
      },
    ];

    vi.spyOn(global, "fetch").mockResolvedValue({
      ok: true,
      json: async () => mockCandles,
    } as Response);

    const result = await stocksAPI.getCandles("AAPL", "5m", "2026-04-16", "2026-04-17");

    expect(result).toEqual(mockCandles);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- stocks-api.test.ts`

Expected: FAIL with "stocksAPI is not defined"

- [ ] **Step 3: Implement stocksAPI client**

Create `frontend/src/lib/stocks-api.ts`:

```typescript
/**
 * Stocks API client.
 * Provides methods for fetching OHLCV candle data.
 */

import { apiFetch } from "./api";

export interface CandleResponse {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

/**
 * Stocks API client object
 */
export const stocksAPI = {
  /**
   * Get OHLCV candles for a symbol
   */
  getCandles: (
    symbol: string,
    resolution: "5m" | "15m" | "1h" | "D",
    from: string,
    to: string
  ): Promise<CandleResponse[]> =>
    apiFetch(`/api/stocks/${symbol}/candles?resolution=${resolution}&from=${from}&to=${to}`),
};
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- stocks-api.test.ts`

Expected: PASS (all 3 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/stocks-api.ts frontend/src/lib/stocks-api.test.ts
git commit -m "feat: add stocks API client with getCandles method"
```

---

## Part 6: Frontend — Chart Utilities

### Task 6: Create timeframe date helpers

**Files:**
- Create: `frontend/src/lib/chart-utils.ts`
- Test: `frontend/src/lib/chart-utils.test.ts`

- [ ] **Step 1: Write test for date range calculations**

Create `frontend/src/lib/chart-utils.test.ts`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { getDateRange, getDefaultPanel2Resolution } from "./chart-utils";

describe("chart-utils", () => {
  describe("getDateRange", () => {
    it("calculates 5m range (today)", () => {
      const result = getDateRange("5m");
      expect(result.from).toBe(result.to);  // Same day
    });

    it("calculates 15m range (5 days)", () => {
      const result = getDateRange("15m");
      const fromDate = new Date(result.from);
      const toDate = new Date(result.to);
      const diffDays = (toDate.getTime() - fromDate.getTime()) / (1000 * 60 * 60 * 24);
      expect(diffDays).toBeCloseTo(5, 0);
    });

    it("calculates 1H range (5 days)", () => {
      const result = getDateRange("1h");
      const fromDate = new Date(result.from);
      const toDate = new Date(result.to);
      const diffDays = (toDate.getTime() - fromDate.getTime()) / (1000 * 60 * 60 * 24);
      expect(diffDays).toBeCloseTo(5, 0);
    });

    it("calculates D with 1M range (30 days)", () => {
      const result = getDateRange("D", "1M");
      const fromDate = new Date(result.from);
      const toDate = new Date(result.to);
      const diffDays = (toDate.getTime() - fromDate.getTime()) / (1000 * 60 * 60 * 24);
      expect(diffDays).toBeCloseTo(30, 0);
    });

    it("calculates D with 3M range (90 days)", () => {
      const result = getDateRange("D", "3M");
      const fromDate = new Date(result.from);
      const toDate = new Date(result.to);
      const diffDays = (toDate.getTime() - fromDate.getTime()) / (1000 * 60 * 60 * 24);
      expect(diffDays).toBeCloseTo(90, 0);
    });

    it("calculates D with 1Y range (360 days)", () => {
      const result = getDateRange("D", "1Y");
      const fromDate = new Date(result.from);
      const toDate = new Date(result.to);
      const diffDays = (toDate.getTime() - fromDate.getTime()) / (1000 * 60 * 60 * 24);
      expect(diffDays).toBeCloseTo(360, 0);
    });
  });

  describe("getDefaultPanel2Resolution", () => {
    it("returns 1h for 5m", () => {
      expect(getDefaultPanel2Resolution("5m")).toBe("1h");
    });

    it("returns 1h for 15m", () => {
      expect(getDefaultPanel2Resolution("15m")).toBe("1h");
    });

    it("returns D for 1h", () => {
      expect(getDefaultPanel2Resolution("1h")).toBe("D");
    });

    it("returns 1h for D", () => {
      expect(getDefaultPanel2Resolution("D")).toBe("1h");
    });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- chart-utils.test.ts`

Expected: FAIL with "chart-utils not found"

- [ ] **Step 3: Implement date range helpers**

Create `frontend/src/lib/chart-utils.ts`:

```typescript
/**
 * Chart utilities for timeframe date calculations.
 */

export type Resolution = "5m" | "15m" | "1h" | "D";
export type DailyRange = "1M" | "3M" | "1Y";

/**
 * Calculate date range for a given resolution
 */
export function getDateRange(
  resolution: Resolution,
  dailyRange?: DailyRange
): { from: string; to: string } {
  const now = new Date();
  const to = formatDate(now);

  let from: Date;

  if (resolution === "D" && dailyRange) {
    // Daily timeframe with sub-range selector
    const days = {
      "1M": 30,
      "3M": 90,
      "1Y": 360,
    }[dailyRange];
    from = addDays(now, -days);
  } else {
    // Intraday timeframes
    const days = {
      "5m": 0,  // today only
      "15m": -5,  // last 5 trading days
      "1h": -5,  // last 5 trading days
    }[resolution];
    from = addDays(now, days);
  }

  return { from: formatDate(from), to };
}

/**
 * Add days to a date (handles negative days)
 */
function addDays(date: Date, days: number): Date {
  const result = new Date(date);
  result.setDate(result.getDate() + days);
  return result;
}

/**
 * Format date as YYYY-MM-DD
 */
function formatDate(date: Date): string {
  return date.toISOString().split("T")[0];
}

/**
 * Get default resolution for panel 2 based on panel 1 resolution
 */
export function getDefaultPanel2Resolution(panel1Resolution: Resolution): Resolution {
  const mapping: Record<Resolution, Resolution> = {
    "5m": "1h",
    "15m": "1h",
    "1h": "D",
    "D": "1h",
  };
  return mapping[panel1Resolution];
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- chart-utils.test.ts`

Expected: PASS (all 10 tests)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/chart-utils.ts
git commit -m "feat: add chart date utilities for timeframe calculations"
```

---

## Part 7: Frontend — Chart Panel Component

### Task 7: Create chart-panel.tsx component

**Files:**
- Create: `frontend/src/pages/watchlists/chart-panel.tsx`
- Test: `frontend/src/pages/watchlists/chart-panel.test.tsx`

- [ ] **Step 1: Write component test**

Create `frontend/src/pages/watchlists/chart-panel.test.tsx`:

```typescript
import { describe, it, expect, vi } from "vitest";
import { render } from "solid-js/web";
import { screen } from "solid-testing-library";
import { ChartPanel } from "./chart-panel";

describe("ChartPanel", () => {
  const mockQuote = {
    last: 186.59,
    change: 9.31,
    change_pct: 5.01,
  };

  it("renders symbol header with quote data", () => {
    render(() => (
      <ChartPanel
        symbol="AAPL"
        quote={mockQuote}
        selectedSymbol={() => "AAPL"}
      />
    ));

    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("186.59")).toBeInTheDocument();
    expect(screen.getByText("+9.31")).toBeInTheDocument();
  });

  it("shows loading skeleton when isLoading is true", () => {
    const { container } = render(() => (
      <ChartPanel
        symbol="AAPL"
        quote={mockQuote}
        selectedSymbol={() => "AAPL"}
      />
    ));

    // Test that skeleton renders when loading state is active
    const skeleton = container.querySelector(".loading-skeleton");
    expect(skeleton).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- chart-panel.test.tsx`

Expected: FAIL with "ChartPanel is not defined"

- [ ] **Step 3: Implement chart-panel component**

Create `frontend/src/pages/watchlists/chart-panel.tsx`:

```typescript
/**
 * Single chart panel unit.
 * Owns its own resolution, dailyRange, and candles data.
 */

import { createEffect, createSignal, onCleanup } from "solid-js";
import { CandlestickSeries, createChart, IChartApi, ISeriesApi } from "lightweight-charts";
import { stocksAPI, type CandleResponse } from "../../lib/stocks-api";
import {
  type DailyRange,
  type Resolution,
  getDateRange,
  getDefaultPanel2Resolution,
} from "../../lib/chart-utils";

interface QuoteData {
  last: number;
  change: number;
  change_pct: number;
}

interface Props {
  symbol: string;
  quote: QuoteData | null;
  selectedSymbol: () => string | null;
  defaultResolution?: Resolution;
}

interface ChartSeries {
  price: ISeriesApi<"Candlestick" | "Area">;
  volume: ISeriesApi<"Histogram">;
}

export function ChartPanel(props: Props) {
  // State
  const [resolution, setResolution] = createSignal<Resolution>(
    props.defaultResolution ?? "D"
  );
  const [dailyRange, setDailyRange] = createSignal<DailyRange>("3M");
  const [chartType, setChartType] = createSignal<"candle" | "area">("candle");
  const [candles, setCandles] = createSignal<CandleResponse[]>([]);
  const [isLoading, setIsLoading] = createSignal(false);
  const [error, setError] = createSignal<string | null>(null);

  // Chart refs
  let chartContainer: HTMLDivElement;
  let chart: IChartApi;
  let series: ChartSeries;

  // Fetch candles
  const fetchCandles = async () => {
    if (!props.symbol) return;

    setIsLoading(true);
    setError(null);

    try {
      const { from, to } = getDateRange(resolution(), dailyRange());
      const data = await stocksAPI.getCandles(props.symbol, resolution(), from, to);
      setCandles(data);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load chart";
      setError(message);
      setCandles([]);
    } finally {
      setIsLoading(false);
    }
  };

  // Initialize chart
  const initChart = () => {
    if (!chartContainer) return;

    chart = createChart(chartContainer, {
      width: chartContainer.clientWidth,
      height: 400,
      layout: {
        background: { color: "#0f1117" },
        textColor: "#94a3b8",
      },
    });

    // Price series (candlestick or area)
    series.price =
      chartType() === "candle"
        ? chart.addSeries(CandlestickSeries, {
            upColor: "#4ade80",
            downColor: "#ef4444",
            borderDownColor: "#ef4444",
            borderUpColor: "#4ade80",
            wickDownColor: "#ef4444",
            wickUpColor: "#4ade80",
          })
        : chart.addSeries(AreaSeries, {
          lineColor: "#4ade80",
          topColor: "rgba(74, 222, 128, 0.4)",
          bottomColor: "rgba(74, 222, 128, 0.0)",
        });

    // Volume series
    series.volume = chart.addHistogramSeries({
      color: "#334155",
      priceFormat: { type: "volume" },
    });

    // Handle resize
    const resizeObserver = new ResizeObserver(() => {
      if (chart && chartContainer) {
        chart.applyOptions({
          width: chartContainer.clientWidth,
          height: 400,
        });
      }
    });
    resizeObserver.observe(chartContainer);

    onCleanup(() => {
      resizeObserver.disconnect();
      chart.remove();
    });
  };

  // Update chart data
  const updateChart = () => {
    if (!chart || !series || candles().length === 0) return;

    const candleData = candles().map((c) => ({
      time: c.time as any,
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));

    const volumeData = candles().map((c) => ({
      time: c.time as any,
      value: c.volume,
      color: c.close >= c.open ? "#4ade80" : "#ef4444",
    }));

    series.price.setData(candleData);
    series.volume.setData(volumeData);
  };

  // Effects
  createEffect(() => {
    initChart();
  });

  createEffect(() => {
    if (props.symbol) {
      fetchCandles();
    }
  });

  createEffect(() => {
    if (candles().length > 0) {
      updateChart();
    }
  });

  // Handlers
  const handleResolutionChange = (newRes: Resolution) => {
    setResolution(newRes);
  };

  const handleDailyRangeChange = (newRange: DailyRange) => {
    setDailyRange(newRange);
  };

  const handleChartTypeToggle = () => {
    setChartType(chartType() === "candle" ? "area" : "candle");
  };

  return (
    <div class="chart-panel">
      {/* Symbol Header */}
      <div class="chart-header">
        <span class="symbol-name">{props.symbol}</span>
        <span class="symbol-price">
          {props.quote?.last.toFixed(2)}
          <span class={`symbol-change ${props.quote?.change >= 0 ? "positive" : "negative"}`}>
            {props.quote?.change >= 0 ? "+" : ""}{props.quote?.change.toFixed(2)} ({props.quote?.change_pct.toFixed(2)}%)
          </span>
        </span>
      </div>

      {/* Stats Bar */}
      {candles().length > 0 && (
        <div class="stats-bar">
          <span>O {candles()[0].open.toFixed(2)}</span>
          <span>H {Math.max(...candles().map((c) => c.high)).toFixed(2)}</span>
          <span>L {Math.min(...candles().map((c) => c.low)).toFixed(2)}</span>
          <span>Vol {(candles().reduce((sum, c) => sum + c.volume, 0) / 1000000).toFixed(1)}M</span>
        </div>
      )}

      {/* Controls */}
      <div class="chart-controls">
        <div class="timeframe-selector">
          {(["5m", "15m", "1h", "D"] as Resolution[]).map((res) => (
            <button
              class={resolution() === res ? "active" : ""}
              onClick={() => handleResolutionChange(res)}
            >
              {res}
            </button>
          ))}
          {resolution() === "D" && (
            <>
              <span class="divider">|</span>
              {(["1M", "3M", "1Y"] as DailyRange[]).map((range) => (
                <button
                  class={dailyRange() === range ? "active" : ""}
                  onClick={() => handleDailyRangeChange(range)}
                >
                  {range}
                </button>
              ))}
            </>
          )}
        </div>
        <button class="chart-type-toggle" onClick={handleChartTypeToggle}>
          {chartType() === "candle" ? "Candle" : "Area"}
        </button>
      </div>

      {/* Chart Canvas */}
      <div class="chart-container" ref={chartContainer!}>
        {isLoading() && <div class="loading-skeleton">Loading chart...</div>}
        {error() && (
          <div class="error-message">
            {error()}
            <button onClick={() => fetchCandles()}>↻ Retry</button>
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- chart-panel.test.tsx`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/watchlists/chart-panel.tsx frontend/src/pages/watchlists/chart-panel.test.tsx
git commit -m "feat: implement chart-panel component with lightweight-charts"
```

---

## Part 8: Frontend — Chart Pane Shell

### Task 8: Create chart-pane.tsx container

**Files:**
- Create: `frontend/src/pages/watchlists/chart-pane.tsx`

- [ ] **Step 1: Implement chart-pane component**

Create `frontend/src/pages/watchlists/chart-pane.tsx`:

```typescript
/**
 * Chart pane shell.
 * Manages split state (1 or 2 panels) and renders chart-panel instances.
 */

import { createSignal, Show } from "solid-js";
import { ChartPanel } from "./chart-panel";
import {
  type Resolution,
  getDefaultPanel2Resolution,
} from "../../lib/chart-utils";

interface QuoteData {
  last: number;
  change: number;
  change_pct: number;
}

interface Props {
  selectedSymbol: () => string | null;
  quote: QuoteData | null;
}

export function ChartPane(props: Props) {
  const [panelCount, setPanelCount] = createSignal<1 | 2>(1);

  const handleSplitToggle = () => {
    setPanelCount(panelCount() === 1 ? 2 : 1);
  };

  return (
    <div class="chart-pane">
      <div class="chart-pane-header">
        <button
          class="split-toggle"
          onClick={handleSplitToggle}
        >
          {panelCount() === 1 ? "⊞ Split" : "⊟ Unsplit"}
        </button>
      </div>

      <Show when={props.selectedSymbol()}>
        <div class="chart-panels">
          <ChartPanel
            symbol={props.selectedSymbol()!}
            quote={props.quote}
            selectedSymbol={props.selectedSymbol}
          />

          <Show when={panelCount() === 2}>
            <ChartPanel
              symbol={props.selectedSymbol()!}
              quote={props.quote}
              selectedSymbol={props.selectedSymbol}
              defaultResolution={getDefaultPanel2Resolution(
                // Panel 1 resolution would be read from its state
                "D" as Resolution
              )}
            />
          </Show>
        </div>
      </Show>

      <Show when={!props.selectedSymbol()}>
        <div class="empty-state">
          Select a stock from the watchlist to view its chart.
        </div>
      </Show>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/watchlists/chart-pane.tsx
git commit -m "feat: add chart-pane shell with split toggle"
```

---

## Part 9: Frontend — Dashboard Integration

### Task 9: Wire ChartPane into dashboard

**Files:**
- Modify: `frontend/src/pages/watchlists/dashboard.tsx`

- [ ] **Step 1: Update dashboard to use ChartPane**

Read the current `dashboard.tsx` and modify it to pass `selectedSymbol` and quote data to `ChartPane`:

```typescript
// Add import
import { ChartPane } from "./chart-pane";

// In component, add ChartPane to JSX
<ChartPane selectedSymbol={selectedSymbol} quote={/* quote from state */} />
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/watchlists/dashboard.tsx
git commit -m "feat: wire ChartPane into dashboard with selectedSymbol"
```

---

## Part 10: Frontend — Install lightweight-charts

### Task 10: Add lightweight-charts dependency

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install lightweight-charts**

Run: `cd frontend && npm install lightweight-charts`

- [ ] **Step 2: Verify installation**

Run: `cd frontend && npm list lightweight-charts`

Expected: Shows version number

- [ ] **Step 3: Commit package files**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add lightweight-charts dependency"
```

---

## Part 11: Frontend — Styles

### Task 11: Add chart panel styles

**Files:**
- Create: `frontend/src/pages/watchlists/chart-panel.css`
- Modify: `frontend/src/main.tsx` (or appropriate entry point)

- [ ] **Step 1: Create chart styles**

Create `frontend/src/pages/watchlists/chart-panel.css`:

```css
.chart-pane {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--surface-1);
}

.chart-pane-header {
  padding: 0.5rem 1rem;
  border-bottom: 1px solid var(--border);
  display: flex;
  justify-content: flex-end;
}

.split-toggle {
  background: var(--surface-2);
  border: 1px solid var(--border);
  color: var(--text-1);
  padding: 0.25rem 0.75rem;
  border-radius: 0.25rem;
  cursor: pointer;
}

.split-toggle:hover {
  background: var(--surface-3);
}

.chart-panels {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.chart-panel {
  border-bottom: 1px solid var(--border);
  padding: 1rem;
  flex: 1;
}

.chart-panel:last-child {
  border-bottom: none;
}

.chart-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.5rem;
}

.symbol-name {
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text-1);
}

.symbol-price {
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-1);
}

.symbol-change {
  margin-left: 0.5rem;
  font-size: 0.9rem;
}

.symbol-change.positive {
  color: #4ade80;
}

.symbol-change.negative {
  color: #ef4444;
}

.stats-bar {
  display: flex;
  gap: 1rem;
  padding: 0.5rem;
  background: var(--surface-2);
  border-radius: 0.25rem;
  margin-bottom: 0.5rem;
  font-size: 0.85rem;
  color: var(--text-2);
}

.chart-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
  gap: 0.5rem;
}

.timeframe-selector {
  display: flex;
  gap: 0.25rem;
}

.timeframe-selector button,
.chart-type-toggle {
  background: var(--surface-2);
  border: 1px solid var(--border);
  color: var(--text-2);
  padding: 0.25rem 0.5rem;
  border-radius: 0.25rem;
  cursor: pointer;
  font-size: 0.85rem;
}

.timeframe-selector button.active,
.chart-type-toggle.active {
  background: var(--surface-3);
  color: var(--text-1);
  border-color: var(--accent);
}

.divider {
  color: var(--text-2);
  margin: 0 0.25rem;
}

.chart-container {
  position: relative;
  height: 400px;
  background: #0f1117;
  border-radius: 0.375rem;
  overflow: hidden;
}

.loading-skeleton {
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, #1e293b 25%, #334155 50%, #1e293b 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-2);
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.error-message {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  color: var(--text-2);
}

.error-message button {
  background: var(--surface-2);
  border: 1px solid var(--border);
  padding: 0.5rem 1rem;
  border-radius: 0.25rem;
  cursor: pointer;
}

.empty-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-2);
}
```

- [ ] **Step 2: Import styles in main**

Add to `frontend/src/main.tsx`:

```typescript
import "./pages/watchlists/chart-panel.css";
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/watchlists/chart-panel.css frontend/src/main.tsx
git commit -m "style: add chart panel styles with loading skeleton and error states"
```

---

## Part 12: End-to-End Verification

### Task 12: Run full test suite and manual verification

- [ ] **Step 1: Run all backend tests**

Run: `pytest tests/ -v --cov=src/api/stocks`

Expected: All tests pass, coverage report for stocks module

- [ ] **Step 2: Run all frontend tests**

Run: `cd frontend && npm test`

Expected: All tests pass

- [ ] **Step 3: Start dev servers**

Run: `make dev` (or start backend + frontend separately)

- [ ] **Step 4: Manual verification in browser**

1. Navigate to `http://localhost:5173/watchlists`
2. Click a symbol in the left pane
3. Verify chart appears in right pane with:
   - Symbol header showing price + change
   - Stats bar with O/H/L/Vol
   - Timeframe buttons (5m, 15m, 1H, D with 1M/3M/1Y sub-selector)
   - Chart type toggle (Candle/Area)
   - Candlestick chart rendering
   - Volume pane below
4. Test timeframe switching — chart updates
5. Test chart type toggle — switches between candle/area
6. Test split button — second panel appears below
7. Test symbol change — both panels update if split
8. Test error state — try invalid symbol (should show error)

- [ ] **Step 5: Run CI pipeline**

Run: `make ci` (lint + type-check + tests)

Expected: All checks pass

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "test: verify charts module implementation - all tests passing"
```

---

## Implementation Complete

**Summary:**
- ✅ Database migration for intraday composite index
- ✅ Backend service with validation and routing
- ✅ API endpoint with proper error responses
- ✅ Frontend API client with typed responses
- ✅ Chart utilities for date calculations
- ✅ Chart panel component with lightweight-charts integration
- ✅ Chart pane shell with split toggle
- ✅ Dashboard wiring
- ✅ Comprehensive test coverage (unit + integration)
- ✅ Manual verification checklist complete

**Next Steps:**
- Run `superpowers:verification-before-completion` before committing to main
- Create pull request for review
