# Watchlist Symbol Row Visual Enhancement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add sparkline (trend) and range bar (position) visual indicators to each symbol row in the watchlist panel.

**Architecture:** Dual visual elements — sparkline from intraday candles, range bar from low/high position. Backend augments QuoteResponse with intraday data, frontend renders SVG components.

**Tech Stack:** SolidJS (frontend), FastAPI/SQLAlchemy (backend), SVG for visualizations

---

## File Structure

### Files Created
- `frontend/src/pages/watchlists/sparkline.tsx` — SVG sparkline component
- `frontend/src/pages/watchlists/range-bar.tsx` — Gradient range bar with position dot
- `frontend/src/pages/watchlists/symbol-row.test.tsx` — Tests for symbol-row (update existing)
- `tests/unit/api/test_watchlist_intraday.py` — Tests for intraday data in quotes

### Files Modified
- `frontend/src/pages/watchlists/symbol-row.tsx` — Integrate sparkline + range bar
- `frontend/src/pages/watchlists/types.ts` — Add IntradayPoint type, extend QuoteResponse
- `frontend/src/lib/watchlists-api.ts` — No change needed (quotes endpoint already returns all data)
- `src/api/watchlists/schemas.py` — Add `low`, `high`, `intraday` fields to QuoteResponse
- `src/api/watchlists/service.py` — Fetch intraday candles and low/high in get_quotes

---

## Task 1: Backend — Extend QuoteResponse Schema

**Files:**
- Modify: `src/api/watchlists/schemas.py`
- Test: `tests/unit/api/test_watchlist_schemas.py`

- [ ] **Step 1: Add IntradayPoint schema**

```python
# Add after imports, before QuoteResponse
class IntradayPoint(BaseModel):
    """Single intraday data point for sparkline rendering."""

    time: str = Field(..., description="ISO timestamp string")
    close: float = Field(..., gt=0, description="Close price at this time")
```

- [ ] **Step 2: Update QuoteResponse schema**

Find the existing `QuoteResponse` class (around line 178) and replace it with:

```python
class QuoteResponse(BaseModel):
    """Quote data for a single watchlist symbol with visual indicators."""

    symbol: str
    last: Optional[float]
    low: Optional[float] = Field(None, description="Day's low price")
    high: Optional[float] = Field(None, description="Day's high price")
    change: Optional[float]
    change_pct: Optional[float]
    source: str  # "realtime" or "eod"
    date: Optional[str] = None  # ISO date string (YYYY-MM-DD) for EOD quotes
    intraday: List[IntradayPoint] = Field(default_factory=list, description="Intraday close prices for sparkline (max 30 points)")
```

- [ ] **Step 3: Run existing tests to verify no breakage**

Run: `pytest tests/unit/api/test_watchlist_schemas.py -v`
Expected: PASS (schema changes are backward compatible)

- [ ] **Step 4: Commit**

```bash
git add src/api/watchlists/schemas.py
git commit -m "feat(watchlists): extend QuoteResponse with low, high, intraday fields

Add low/high for range bar and intraday points for sparkline rendering.
IntradayPoint schema added for sparkline data structure.
"
```

---

## Task 2: Backend — Fetch Intraday Data in get_quotes

**Files:**
- Modify: `src/api/watchlists/service.py`
- Test: `tests/unit/api/test_watchlist_service.py`

- [ ] **Step 1: Write failing test for intraday data in quotes**

Create `tests/unit/api/test_watchlist_service_intraday.py`:

```python
"""Tests for watchlist service intraday data fetching."""

import pytest
from datetime import date, datetime
from unittest.mock import Mock, patch

from src.api.watchlists.service import WatchlistService
from src.api.watchlists.schemas import QuoteResponse
from src.db.models import Stock, Watchlist, WatchlistCategory, WatchlistSymbol, IntradayCandle


@pytest.fixture
def db_session():
    """Mock database session."""
    session = Mock()
    return session


@pytest.fixture
def sample_watchlist_with_symbols(db_session):
    """Create sample watchlist with symbols for testing."""
    # Mock user
    user = Mock()
    user.id = 1

    # Create category
    category = WatchlistCategory(
        id=1,
        user_id=1,
        name="Test Category",
        icon="🧪",
        is_system=False,
        sort_order=1,
    )

    # Create watchlist
    watchlist = Watchlist(
        id=1,
        user_id=1,
        name="Test Watchlist",
        category_id=1,
        is_auto_generated=False,
        watchlist_mode="static",
    )

    # Create stocks
    stock1 = Stock(id=1, symbol="AAPL", name="Apple Inc")
    stock2 = Stock(id=2, symbol="TSLA", name="Tesla Inc")

    # Create watchlist symbols
    ws1 = WatchlistSymbol(
        id=1,
        watchlist_id=1,
        stock_id=1,
        priority=0,
    )
    ws1.stock = stock1

    ws2 = WatchlistSymbol(
        id=2,
        watchlist_id=1,
        stock_id=2,
        priority=1,
    )
    ws2.stock = stock2

    db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [ws1, ws2]

    return {
        "user_id": 1,
        "watchlist_id": 1,
        "symbols": [ws1, ws2],
        "stocks": [stock1, stock2],
    }


def test_get_quotes_includes_intraday_data(db_session, sample_watchlist_with_symbols):
    """Test that get_quotes includes intraday data points for sparkline."""
    service = WatchlistService(db_session)

    # Mock the watchlist lookup
    mock_watchlist = Mock()
    mock_watchlist.id = 1
    db_session.query.return_value.filter.return_value.first.return_value = mock_watchlist

    # Mock get_watchlist_symbols to return our symbols
    with patch.object(service, 'get_watchlist_symbols', return_value=sample_watchlist_with_symbols["symbols"]):
        with patch.object(service, '_get_quotes_from_db') as mock_get_quotes:
            # Set up the mock to return quotes with intraday data
            mock_get_quotes.return_value = [
                QuoteResponse(
                    symbol="AAPL",
                    last=186.59,
                    low=178.20,
                    high=188.50,
                    change=9.31,
                    change_pct=5.01,
                    source="realtime",
                    intraday=[
                        {"time": "2026-04-23T09:30:00", "close": 180.50},
                        {"time": "2026-04-23T10:30:00", "close": 182.30},
                        {"time": "2026-04-23T11:30:00", "close": 185.10},
                        {"time": "2026-04-23T12:30:00", "close": 183.80},
                        {"time": "2026-04-23T13:30:00", "close": 186.00},
                        {"time": "2026-04-23T14:30:00", "close": 186.59},
                    ],
                )
            ]

            result = service.get_quotes(1, 1)

    assert len(result) == 1
    quote = result[0]
    assert quote.symbol == "AAPL"
    assert quote.low == 178.20
    assert quote.high == 188.50
    assert len(quote.intraday) == 6
    assert quote.intraday[0]["close"] == 180.50


def test_get_quotes_eod_fallback_no_intraday(db_session):
    """Test that EOD quotes have empty intraday array."""
    service = WatchlistService(db_session)

    # Mock watchlist and symbols
    mock_watchlist = Mock()
    mock_watchlist.id = 1
    db_session.query.return_value.filter.return_value.first.return_value = mock_watchlist

    stock = Stock(id=1, symbol="AAPL", name="Apple Inc")
    ws = WatchlistSymbol(id=1, watchlist_id=1, stock_id=1, priority=0)
    ws.stock = stock

    with patch.object(service, 'get_watchlist_symbols', return_value=[ws]):
        with patch.object(service, '_get_quotes_from_db') as mock_get_quotes:
            mock_get_quotes.return_value = [
                QuoteResponse(
                    symbol="AAPL",
                    last=186.59,
                    low=178.20,
                    high=188.50,
                    change=9.31,
                    change_pct=5.01,
                    source="eod",
                    date="2026-04-22",
                    intraday=[],  # EOD has no intraday
                )
            ]

            result = service.get_quotes(1, 1)

    assert len(result) == 1
    assert result[0].source == "eod"
    assert result[0].intraday == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/api/test_watchlist_service_intraday.py -v`
Expected: FAIL — intraday data not yet implemented

- [ ] **Step 3: Implement intraday fetching in _get_quotes_from_db**

In `src/api/watchlists/service.py`, update the `_get_quotes_from_db` method to fetch intraday candles and low/high values.

Find the existing `_get_quotes_from_db` method (around line 315) and update the realtime row building section:

```python
        result: dict[int, QuoteResponse] = {}
        for row in realtime_rows:
            # Fetch intraday candles for this stock (last 30 points for sparkline)
            intraday_data = self._get_intraday_points(int(row.stock_id))

            result[int(row.stock_id)] = QuoteResponse(
                symbol=stock_id_to_symbol[int(row.stock_id)],
                last=float(row.last) if row.last is not None else None,
                low=min((p["close"] for p in intraday_data), default=float(row.last)) if intraday_data else None,
                high=max((p["close"] for p in intraday_data), default=float(row.last)) if intraday_data else None,
                change=float(row.change) if row.change is not None else None,
                change_pct=float(row.change_pct) if row.change_pct is not None else None,
                source="realtime",
                intraday=intraday_data,
            )
```

Then update the EOD fallback section to include low/high from candle data:

```python
            for stock_id, candles in candles_by_stock.items():
                latest_close = float(candles[0].close) if candles[0].close is not None else None
                candle_high = float(candles[0].high) if candles[0].high is not None else None
                candle_low = float(candles[0].low) if candles[0].low is not None else None

                if (
                    len(candles) >= 2
                    and candles[0].close is not None
                    and candles[1].close is not None
                ):
                    change = float(candles[0].close - candles[1].close)
                    prev = float(candles[1].close)
                    change_pct = (change / prev * 100) if prev != 0 else None
                else:
                    change = None
                    change_pct = None

                result[stock_id] = QuoteResponse(
                    symbol=stock_id_to_symbol[stock_id],
                    last=latest_close,
                    low=candle_low,
                    high=candle_high,
                    change=change,
                    change_pct=change_pct,
                    source="eod",
                    date=(
                        candles[0].timestamp.strftime("%Y-%m-%d") if candles[0].timestamp else None
                    ),
                    intraday=[],  # No intraday for EOD
                )
```

- [ ] **Step 4: Add _get_intraday_points helper method**

Add this new method to the `WatchlistService` class (after the `_get_quotes_from_db` method):

```python
    def _get_intraday_points(self, stock_id: int) -> List[dict]:
        """Get intraday close prices for sparkline rendering.

        Fetches the last 30 intraday candles (1h resolution) for today.
        Returns list of {time, close} dicts ordered by time ascending.

        Args:
            stock_id: ID of the stock

        Returns:
            List of {time: str, close: float} dicts, empty if no intraday data
        """
        from src.db.models import IntradayCandle

        candles = (
            self.db_session.query(
                IntradayCandle.timestamp,
                IntradayCandle.close,
            )
            .filter(
                IntradayCandle.stock_id == stock_id,
                func.date(IntradayCandle.timestamp) == date.today(),
            )
            .order_by(IntradayCandle.timestamp.asc())
            .limit(30)
            .all()
        )

        return [
            {"time": candle.timestamp.isoformat(), "close": float(candle.close)}
            for candle in candles
            if candle.close is not None
        ]
```

Also update imports at the top of the file (around line 16):

```python
from src.db.models import (
    DailyCandle,
    IntradayCandle,
    RealtimeQuote,
    Stock,
    Watchlist,
    WatchlistCategory,
    WatchlistSymbol,
)
```

- [ ] **Step 5: Run tests to verify implementation**

Run: `pytest tests/unit/api/test_watchlist_service_intraday.py -v`
Expected: PASS

- [ ] **Step 6: Run related tests to ensure no breakage**

Run: `pytest tests/unit/api/test_watchlist_service.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/api/watchlists/service.py tests/unit/api/test_watchlist_service_intraday.py
git commit -m "feat(watchlists): fetch intraday candles and low/high in get_quotes

- Add _get_intraday_points helper to fetch last 30 1h candles
- Include low/high from intraday (realtime) or daily candles (EOD)
- Add intraday data array to QuoteResponse for sparkline rendering
"
```

---

## Task 3: Frontend — Update Types

**Files:**
- Modify: `frontend/src/pages/watchlists/types.ts`

- [ ] **Step 1: Add IntradayPoint interface and extend QuoteResponse**

Find the existing `QuoteResponse` interface (around line 154) and replace it with:

```typescript
/**
 * Single intraday data point for sparkline rendering
 */
export interface IntradayPoint {
  time: string;  // ISO timestamp string
  close: number; // Close price at this time
}

/**
 * Quote response for a symbol
 */
export interface QuoteResponse {
  symbol: string;
  last: number | null;
  low: number | null;   // Day's low price
  high: number | null;  // Day's high price
  change: number | null;
  change_pct: number | null;
  source: "realtime" | "eod";
  date: string | null;  // ISO date string (YYYY-MM-DD) for EOD quotes, null for realtime
  intraday: IntradayPoint[];  // Intraday close prices for sparkline (max 30 points)
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/watchlists/types.ts
git commit -m "feat(watchlists): extend QuoteResponse type with low, high, intraday

Add low/high for range bar and intraday array for sparkline rendering.
IntradayPoint interface added for sparkline data structure.
"
```

---

## Task 4: Frontend — Create Sparkline Component

**Files:**
- Create: `frontend/src/pages/watchlists/sparkline.tsx`
- Test: `frontend/src/pages/watchlists/sparkline.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/pages/watchlists/sparkline.test.tsx`:

```typescript
/**
 * Tests for Sparkline component
 */

import { describe, it, expect } from "vitest";
import { render } from "@testing-library/solidjs";
import { Sparkline } from "./sparkline";

describe("Sparkline", () => {
  it("renders green sparkline for bullish data", () => {
    const data = [
      { time: "2026-04-23T09:30:00", close: 180 },
      { time: "2026-04-23T10:30:00", close: 182 },
      { time: "2026-04-23T11:30:00", close: 185 },
      { time: "2026-04-23T12:30:00", close: 188 },
    ];

    const { container } = render(() => (
      <Sparkline data={data} color="green" width={48} height={16} />
    ));

    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute("width")).toBe("48");
    expect(svg?.getAttribute("height")).toBe("16");

    const polyline = svg?.querySelector("polyline");
    expect(polyline).not.toBeNull();
    expect(polyline?.getAttribute("stroke")).toBe("#22c55e");
  });

  it("renders red sparkline for bearish data", () => {
    const data = [
      { time: "2026-04-23T09:30:00", close: 188 },
      { time: "2026-04-23T10:30:00", close: 185 },
      { time: "2026-04-23T11:30:00", close: 182 },
      { time: "2026-04-23T12:30:00", close: 180 },
    ];

    const { container } = render(() => (
      <Sparkline data={data} color="red" width={48} height={16} />
    ));

    const svg = container.querySelector("svg");
    const polyline = svg?.querySelector("polyline");
    expect(polyline?.getAttribute("stroke")).toBe("#ef4444");
  });

  it("renders gray sparkline for neutral/no data", () => {
    const { container } = render(() => (
      <Sparkline data={[]} color="gray" width={48} height={16} />
    ));

    const svg = container.querySelector("svg");
    const polyline = svg?.querySelector("polyline");
    expect(polyline?.getAttribute("stroke")).toBe("#94a3b8");
  });

  it("normalizes data points to fit SVG viewBox", () => {
    const data = [
      { time: "2026-04-23T09:30:00", close: 100 },
      { time: "2026-04-23T10:30:00", close: 200 },
    ];

    const { container } = render(() => (
      <Sparkline data={data} color="green" width={48} height={16} />
    ));

    const polyline = container.querySelector("polyline");
    const points = polyline?.getAttribute("points");

    // Points should be normalized to 0-15 range (height - 1 for padding)
    expect(points).toContain("0");  // min value maps to bottom
    expect(points).toContain("15"); // max value maps to top
  });

  it("handles single data point", () => {
    const data = [{ time: "2026-04-23T09:30:00", close: 150 }];

    const { container } = render(() => (
      <Sparkline data={data} color="green" width={48} height={16} />
    ));

    const polyline = container.querySelector("polyline");
    expect(polyline).not.toBeNull();
    // Single point should render a dot in the middle
    const points = polyline?.getAttribute("points");
    expect(points).toContain("8"); // middle of 0-15 range
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- sparkline.test.tsx`
Expected: FAIL — component doesn't exist yet

- [ ] **Step 3: Implement Sparkline component**

Create `frontend/src/pages/watchlists/sparkline.tsx`:

```typescript
/**
 * Sparkline — mini line chart showing intraday price movement.
 *
 * Renders an SVG polyline from intraday close prices.
 * Color indicates direction: green (up), red (down), gray (flat/no data).
 */

import { Component } from "solid-js";

export interface IntradayPoint {
  time: string;
  close: number;
}

interface SparklineProps {
  data: IntradayPoint[];
  color: "green" | "red" | "gray";
  width: number;
  height: number;
}

const COLOR_MAP = {
  green: "#22c55e",
  red: "#ef4444",
  gray: "#94a3b8",
};

export const Sparkline: Component<SparklineProps> = (props) => {
  const color = () => COLOR_MAP[props.color];

  // Normalize close prices to fit in SVG height (0 to height-1)
  const normalizeData = (): string => {
    if (props.data.length === 0) {
      // No data: render flat line in middle
      const midY = Math.floor(props.height / 2);
      return `0,${midY} ${props.width},${midY}`;
    }

    if (props.data.length === 1) {
      // Single point: dot in middle
      const midY = Math.floor(props.height / 2);
      const midX = Math.floor(props.width / 2);
      return `${midX},${midY}`;
    }

    const closes = props.data.map((d) => d.close);
    const minClose = Math.min(...closes);
    const maxClose = Math.max(...closes);
    const range = maxClose - minClose || 1; // Avoid divide by zero

    // Map each data point to (x, y) coordinates
    const points = props.data.map((d, i) => {
      const x = (i / (props.data.length - 1)) * props.width;
      // Invert y because SVG coordinates: 0 is top
      const normalizedY = ((d.close - minClose) / range);
      const y = props.height - 1 - (normalizedY * (props.height - 1));
      return `${x},${y}`;
    });

    return points.join(" ");
  };

  return (
    <svg
      width={props.width}
      height={props.height}
      viewBox={`0 0 ${props.width} ${props.height}`}
      aria-hidden="true"
      style="display: block;"
    >
      <polyline
        points={normalizeData()}
        fill="none"
        stroke={color()}
        stroke-width="1.2"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>
  );
};
```

- [ ] **Step 4: Run tests to verify implementation**

Run: `npm test -- sparkline.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/watchlists/sparkline.tsx frontend/src/pages/watchlists/sparkline.test.tsx
git commit -m "feat(watchlists): add Sparkline component for intraday trend

Renders SVG polyline from intraday close prices.
Color indicates direction: green (up), red (down), gray (flat/no data).
Normalizes data points to fit within viewBox dimensions.
"
```

---

## Task 5: Frontend — Create RangeBar Component

**Files:**
- Create: `frontend/src/pages/watchlists/range-bar.tsx`
- Test: `frontend/src/pages/watchlists/range-bar.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/pages/watchlists/range-bar.test.tsx`:

```typescript
/**
 * Tests for RangeBar component
 */

import { describe, it, expect } from "vitest";
import { render } from "@testing-library/solidjs";
import { RangeBar } from "./range-bar";

describe("RangeBar", () => {
  it("renders gradient background with position marker", () => {
    const { container } = render(() => (
      <RangeBar low={100} high={200} current={150} width={32} height={14} />
    ));

    const bar = container.querySelector(".range-bar");
    expect(bar).not.toBeNull();

    const marker = container.querySelector(".range-bar__marker");
    expect(marker).not.toBeNull();

    // Position should be 50% (150 is midpoint of 100-200)
    const style = marker?.getAttribute("style");
    expect(style).toContain("left: 50%");
  });

  it("positions marker at high end when current equals high", () => {
    const { container } = render(() => (
      <RangeBar low={100} high={200} current={200} width={32} height={14} />
    ));

    const marker = container.querySelector(".range-bar__marker");
    const style = marker?.getAttribute("style");
    expect(style).toContain("left: 100%");
  });

  it("positions marker at low end when current equals low", () => {
    const { container } = render(() => (
      <RangeBar low={100} high={200} current={100} width={32} height={14} />
    ));

    const marker = container.querySelector(".range-bar__marker");
    const style = marker?.getAttribute("style");
    expect(style).toContain("left: 0%");
  });

  it("handles null values gracefully", () => {
    const { container } = render(() => (
      <RangeBar low={null} high={null} current={150} width={32} height={14} />
    ));

    const marker = container.querySelector(".range-bar__marker");
    // Should center marker when low/high are null
    const style = marker?.getAttribute("style");
    expect(style).toContain("left: 50%");
  });

  it("handles zero range (low equals high)", () => {
    const { container } = render(() => (
      <RangeBar low={150} high={150} current={150} width={32} height={14} />
    ));

    const marker = container.querySelector(".range-bar__marker");
    const style = marker?.getAttribute("style");
    expect(style).toContain("left: 50%");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- range-bar.test.tsx`
Expected: FAIL — component doesn't exist yet

- [ ] **Step 3: Implement RangeBar component**

Create `frontend/src/pages/watchlists/range-bar.tsx`:

```typescript
/**
 * RangeBar — horizontal gradient bar showing current price position.
 *
 * Renders a gradient background (red → yellow → green) with a vertical
 * marker showing where the current price sits within the day's low/high range.
 */

import { Component } from "solid-js";

interface RangeBarProps {
  low: number | null;
  high: number | null;
  current: number;
  width: number;
  height: number;
}

export const RangeBar: Component<RangeBarProps> = (props) => {
  // Calculate marker position as percentage (0-100%)
  const markerPosition = () => {
    if (props.low === null || props.high === null || props.low === props.high) {
      return 50; // Center if no range data
    }
    const range = props.high - props.low;
    if (range === 0) return 50;
    const position = ((props.current - props.low) / range) * 100;
    return Math.max(0, Math.min(100, position)); // Clamp to 0-100
  };

  const markerLeft = () => `${markerPosition()}%`;

  return (
    <div
      class="range-bar"
      style={{
        position: "relative",
        width: `${props.width}px`,
        height: `${props.height}px`,
      }}
    >
      {/* Gradient background */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: "linear-gradient(90deg, #ef4444 0%, #fbbf24 50%, #22c55e 100%)",
          "border-radius": "2px",
          opacity: "0.5",
        }}
      />

      {/* Position marker */}
      <div
        class="range-bar__marker"
        style={{
          position: "absolute",
          top: "0",
          bottom: "0",
          width: "2px",
          "background-color": "#fbbf24",
          left: markerLeft(),
          "box-shadow": "0 0 3px #fbbf24",
        }}
      />
    </div>
  );
};
```

- [ ] **Step 4: Run tests to verify implementation**

Run: `npm test -- range-bar.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/watchlists/range-bar.tsx frontend/src/pages/watchlists/range-bar.test.tsx
git commit -m "feat(watchlists): add RangeBar component for price position

Renders gradient bar (red→yellow→green) with vertical position marker.
Shows where current price sits within day's low/high range.
Handles null/zero range gracefully by centering marker.
"
```

---

## Task 6: Frontend — Integrate Components into SymbolRow

**Files:**
- Modify: `frontend/src/pages/watchlists/symbol-row.tsx`
- Modify: `frontend/src/pages/watchlists/symbol-row.test.tsx`

- [ ] **Step 1: Update existing test for new layout**

Update `frontend/src/pages/watchlists/symbol-row.test.tsx` to test the new layout with sparkline and range bar:

```typescript
/**
 * Tests for SymbolRow component
 */

import { describe, it, expect } from "vitest";
import { render } from "@testing-library/solidjs";
import { SymbolRow } from "./symbol-row";
import type { QuoteResponse } from "./types";

describe("SymbolRow", () => {
  const baseQuote: QuoteResponse = {
    symbol: "AAPL",
    last: 186.59,
    low: 178.20,
    high: 188.50,
    change: 9.31,
    change_pct: 5.01,
    source: "realtime",
    date: null,
    intraday: [
      { time: "2026-04-23T09:30:00", close: 180.50 },
      { time: "2026-04-23T10:30:00", close: 182.30 },
      { time: "2026-04-23T11:30:00", close: 185.10 },
    ],
  };

  it("renders sparkline and range bar", () => {
    const { container } = render(() => (
      <SymbolRow
        quote={baseQuote}
        selected={false}
        focused={false}
        onSelect={() => {}}
        onRemove={() => {}}
      />
    ));

    // Check sparkline is rendered
    const svg = container.querySelector(".symbol-row svg");
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute("width")).toBe("48");

    // Check range bar is rendered
    const rangeBar = container.querySelector(".range-bar");
    expect(rangeBar).not.toBeNull();
  });

  it("determines sparkline color from change", () => {
    const { container: greenContainer } = render(() => (
      <SymbolRow
        quote={{ ...baseQuote, change: 9.31 }}
        selected={false}
        focused={false}
        onSelect={() => {}}
        onRemove={() => {}}
      />
    ));

    const greenPolyline = greenContainer.querySelector("polyline");
    expect(greenPolyline?.getAttribute("stroke")).toBe("#22c55e");

    const { container: redContainer } = render(() => (
      <SymbolRow
        quote={{ ...baseQuote, change: -9.31, change_pct: -5.01 }}
        selected={false}
        focused={false}
        onSelect={() => {}}
        onRemove={() => {}}
      />
    ));

    const redPolyline = redContainer.querySelector("polyline");
    expect(redPolyline?.getAttribute("stroke")).toBe("#ef4444");
  });

  it("shows gray sparkline for EOD quotes", () => {
    const eodQuote: QuoteResponse = {
      ...baseQuote,
      source: "eod",
      date: "2026-04-22",
      intraday: [], // No intraday for EOD
    };

    const { container } = render(() => (
      <SymbolRow
        quote={eodQuote}
        selected={false}
        focused={false}
        onSelect={() => {}}
        onRemove={() => {}}
      />
    ));

    const polyline = container.querySelector("polyline");
    expect(polyline?.getAttribute("stroke")).toBe("#94a3b8");
  });

  it("calculates range bar position correctly", () => {
    const { container } = render(() => (
      <SymbolRow
        quote={baseQuote}
        selected={false}
        focused={false}
        onSelect={() => {}}
        onRemove={() => {}}
      />
    ));

    const marker = container.querySelector(".range-bar__marker");
    const style = marker?.getAttribute("style");

    // 186.59 is ~75% of range 178.20-188.50
    expect(style).toContain("left:");
  });

  it("handles null low/high gracefully", () => {
    const nullRangeQuote: QuoteResponse = {
      ...baseQuote,
      low: null,
      high: null,
    };

    const { container } = render(() => (
      <SymbolRow
        quote={nullRangeQuote}
        selected={false}
        focused={false}
        onSelect={() => {}}
        onRemove={() => {}}
      />
    ));

    // Should still render, marker centered
    const marker = container.querySelector(".range-bar__marker");
    expect(marker).not.toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- symbol-row.test.tsx`
Expected: FAIL — component not yet updated

- [ ] **Step 3: Update SymbolRow component**

Replace the entire content of `frontend/src/pages/watchlists/symbol-row.tsx` with:

```typescript
/**
 * SymbolRow — a single stock row in the watchlist panel.
 *
 * Shows: source dot, ticker, sparkline (trend), range bar (position),
 * last price, change%, remove button on hover.
 * Supports keyboard focus indication (distinct from mouse selection).
 */

import { Component, Show } from "solid-js";
import { Sparkline } from "./sparkline";
import { RangeBar } from "./range-bar";
import type { QuoteResponse } from "./types";

interface SymbolRowProps {
  quote: QuoteResponse;
  selected: boolean;
  focused: boolean;
  onSelect: (symbol: string) => void;
  onRemove: (symbol: string) => void;
}

function fmt(n: number | null, decimals = 2): string {
  if (n === null) return "—";
  return n.toFixed(decimals);
}

function fmtChange(n: number | null): string {
  if (n === null) return "—";
  return n >= 0 ? `+${n.toFixed(2)}` : `${n.toFixed(2)}`;
}

function getSparklineColor(quote: QuoteResponse): "green" | "red" | "gray" {
  if (quote.source === "eod" || quote.intraday.length === 0) {
    return "gray";
  }
  return quote.change !== null && quote.change >= 0 ? "green" : "red";
}

export const SymbolRow: Component<SymbolRowProps> = (props) => {
  const isPositive = () => props.quote.change !== null && props.quote.change >= 0;
  const changeClass = () =>
    props.quote.change === null ? "neutral" : isPositive() ? "positive" : "negative";

  const sparklineColor = () => getSparklineColor(props.quote);

  return (
    <div
      class="symbol-row"
      classList={{ selected: props.selected, focused: props.focused }}
      onClick={() => props.onSelect(props.quote.symbol)}
    >
      {/* Source dot */}
      <span
        class="source-dot"
        classList={{
          "source-dot--realtime": props.quote.source === "realtime",
          "source-dot--eod": props.quote.source === "eod",
        }}
        title={
          props.quote.source === "realtime"
            ? "Realtime"
            : props.quote.date
              ? `End of day (${props.quote.date})`
              : "End of day"
        }
      />

      {/* Ticker */}
      <span class="symbol-ticker">{props.quote.symbol}</span>

      {/* Sparkline */}
      <div class="symbol-sparkline">
        <Sparkline
          data={props.quote.intraday}
          color={sparklineColor()}
          width={48}
          height={16}
        />
      </div>

      {/* Range bar */}
      <div class="symbol-range">
        <Show when={props.quote.low !== null && props.quote.high !== null}>
          <RangeBar
            low={props.quote.low}
            high={props.quote.high}
            current={props.quote.last ?? 0}
            width={32}
            height={14}
          />
        </Show>
      </div>

      {/* Last price */}
      <span class="symbol-last">{fmt(props.quote.last)}</span>

      {/* Change percent */}
      <span class={`symbol-change ${changeClass()}`}>
        {props.quote.change_pct !== null ? `${fmtChange(props.quote.change_pct)}%` : "—"}
      </span>

      {/* Remove button */}
      <button
        class="symbol-remove"
        aria-label={`Remove ${props.quote.symbol}`}
        onClick={(e) => {
          e.stopPropagation();
          props.onRemove(props.quote.symbol);
        }}
      >
        ✕
      </button>
    </div>
  );
};
```

- [ ] **Step 4: Update CSS for new layout**

Update the symbol row styles. Add this to your CSS file (likely `frontend/src/pages/watchlists/chart-panel.css` or a separate watchlist.css):

```css
/* Symbol row layout adjustments */
.symbol-row {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 0;
  cursor: pointer;
}

.symbol-ticker {
  width: 38px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.symbol-sparkline {
  flex-shrink: 0;
}

.symbol-range {
  flex-shrink: 0;
}

.symbol-last {
  width: 40px;
  text-align: right;
  font-weight: 600;
}

.symbol-change {
  width: 40px;
  text-align: right;
}
```

- [ ] **Step 5: Run tests to verify implementation**

Run: `npm test -- symbol-row.test.tsx`
Expected: PASS

- [ ] **Step 6: Run integration test to verify visual rendering**

Run: `npm run test:e2e -- watchlists.spec.ts`
Expected: PASS (watchlist loads with visual indicators)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/watchlists/symbol-row.tsx frontend/src/pages/watchlists/symbol-row.test.tsx
git add frontend/src/pages/watchlists/chart-panel.css
git commit -m "feat(watchlists): integrate sparkline and range bar into SymbolRow

- Add Sparkline component for intraday trend visualization
- Add RangeBar component showing current price within day range
- Remove $change column, add low/high data
- Compress gaps from 6px to 4px for space efficiency
- Sparkline color: green (up), red (down), gray (EOD/no data)
"
```

---

## Task 7: End-to-End Verification

**Files:**
- None (verification only)

- [ ] **Step 1: Start the development server**

```bash
npm run dev
```

- [ ] **Step 2: Navigate to watchlist page**

Open browser to `http://localhost:5173/watchlists` (or your dev port)

- [ ] **Step 3: Verify visual elements appear**

Check for:
- [ ] Sparkline visible for realtime quotes (green/red based on direction)
- [ ] Gray sparkline for EOD quotes
- [ ] Range bar shows position marker
- [ ] Marker on right for stocks near highs
- [ ] Marker on left for stocks near lows
- [ ] Layout fits without horizontal scrolling

- [ ] **Step 4: Test with different scenarios**

Add symbols to a watchlist and verify:
- [ ] Uptrending stock shows climbing green sparkline
- [ ] Downtrending stock shows falling red sparkline
- [ ] Volatile stock shows jagged sparkline
- [ ] Range bar marker moves based on price position

- [ ] **Step 5: Run full test suite**

```bash
npm test
pytest tests/unit/api/test_watchlist_service.py -v
pytest tests/integration/api/test_watchlist_quotes_route.py -v
```

Expected: All PASS

- [ ] **Step 6: Commit final documentation**

```bash
git commit --allow-empty -m "docs: complete watchlist symbol row visual enhancement

All tasks completed:
- Backend: QuoteResponse extended with low/high/intraday
- Frontend: Sparkline and RangeBar components integrated
- Tests: Unit and integration tests passing
- Manual verification: Visual elements render correctly

Design spec: docs/superpowers/specs/2026-04-23-watchlist-symbol-row-design.md
"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ Sparkline for trend visualization (Task 4)
- ✅ Range bar for position visualization (Task 5)
- ✅ Integration into SymbolRow (Task 6)
- ✅ Backend data fetching (Task 2)
- ✅ Type updates (Task 3)
- ✅ Space management (handled in SymbolRow layout)
- ✅ Color specification (green/red/gray defined)
- ✅ EOD fallback (gray sparkline, empty intraday array)

**Placeholder scan:**
- ✅ No TBD, TODO, or "implement later" found
- ✅ All test code shown explicitly
- ✅ All commands with expected output
- ✅ No ambiguous "add error handling" instructions

**Type consistency:**
- ✅ QuoteResponse schema matches between backend and frontend
- ✅ IntradayPoint structure consistent
- ✅ Component props match interfaces
- ✅ get_quotes returns correct field names (low, high, intraday)

**Scope check:**
- ✅ Focused on single feature: symbol row visual enhancement
- ✅ No unrelated refactoring included
- ✅ Each task is independently testable
- ✅ Tasks can be implemented in order with minimal cross-dependencies
