# Charts Module — Design Spec

**Date:** 2026-04-17 (updated 2026-04-19 per code review)
**Sub-project:** Chart panel for the watchlist right pane
**Depends on:** `2026-04-16-watchlist-redesign.md` (right pane placeholder filled by this module)

---

## Problem

The watchlist right pane currently shows "Select a stock to view detail" as a static placeholder. The workflow this module serves:

1. **EOD scan review** — browse scanner results using daily charts to identify candidates
2. **Watchlist curation** — move candidates into a manual sublist
3. **Trade execution** — switch to intraday charts (5m/15m/1H) to time entries and monitor positions

The chart panel must be fast, minimal, and support simultaneous multi-timeframe views.

---

## Rendering Approach

**lightweight-charts** (TradingView OSS, ~40KB gzipped). Renders candlestick and area charts on a canvas element. No external data dependency — all data comes from the existing PostgreSQL DB.

Alternatives considered and rejected:
- Finviz embedded image — fragile external dependency, no interactivity, ToS risk
- Server-rendered PNG (mplfinance) — no interactivity, server CPU per render

---

## Layout

The watchlist `/watchlists` route uses a two-pane split (from the redesign spec). The right pane is now owned by `chart-pane.tsx`.

```
/watchlists
┌─────────────────┬──────────────────────────────────────┐
│ LEFT PANE       │ RIGHT PANE (chart-pane.tsx)          │
│ (watchlist      │                                      │
│  panel)         │  [⊟ Split]          ← button         │
│                 ├──────────────────────────────────────┤
│                 │  chart-panel (panel 1)               │
│                 │  AAPL  186.59  +9.31 (+5.01%)        │
│                 │  O 180  H 188  L 179  V 52M  52W … │
│                 │  [5m][15m][1H][D·1M|3M|1Y]  [C][A]  │
│                 │  ┌────────────────────────────────┐  │
│                 │  │   candlestick / area chart     │  │
│                 │  │   volume pane below            │  │
│                 │  └────────────────────────────────┘  │
│                 ├──────────────────────────────────────┤
│                 │  chart-panel (panel 2) — split only  │
│                 │  AAPL  186.59  +9.31 (+5.01%)        │
│                 │  [5m][15m][1H][D·1M|3M|1Y]  [C][A]  │
│                 │  ┌────────────────────────────────┐  │
│                 │  │   chart                        │  │
│                 │  └────────────────────────────────┘  │
└─────────────────┴──────────────────────────────────────┘
```

**Split behaviour:**
- Default: 1 panel
- `[⊟ Split]` button adds panel 2 stacked below panel 1
- Panel 2 opens with the same symbol, with timeframe **one step "up"** from panel 1:
  - `5m` → `1H`
  - `15m` → `1H`
  - `1H` → `D` (with 3M sub-range)
  - `D` → `1H`
- Both panels always show `selectedSymbol` — independent symbol per panel is out of scope
- Unsplitting hides panel 2; panel 1 is unaffected
- **Height allocation:** fixed 50/50 split (not resizable in v1)
- Split state is **not** persisted across page reload (v1)

**Symbol change behaviour (when split is active):**
- When `selectedSymbol` changes in the watchlist (user clicks a different stock), **both panels refetch** with their current timeframes preserved
- Per-panel settings (timeframe, chart type, daily range) persist across symbol changes — power users can compare two stocks at the same multi-timeframe layout
- Each panel fetches independently — one failing doesn't affect the other

**Desktop-only.** Mobile layout deferred.

---

## Timeframe Switcher

Each panel has its own independent timeframe controls.

| Button | Resolution | Data source | Default lookback |
|--------|-----------|-------------|-----------------|
| 5m | 5m | `intraday_candles` | today |
| 15m | 15m | `intraday_candles` | last 5 trading days |
| 1H | 1h | `intraday_candles` | last 5 trading days |
| D | D | `daily_candles` | — |

When **D** is active, a secondary sub-selector appears inline:

| Sub-button | Lookback |
|-----------|---------|
| 1M | 30 calendar days |
| 3M | 90 calendar days (default) |
| 1Y | 360 calendar days |

**Note:** 1H default is 5 days (not 7) to avoid colliding with the 7-day intraday retention window. Daily 1Y is 360 days (not 365) to avoid colliding with the 1-year daily retention boundary.

Frontend computes `from` / `to` dates and passes them as query params. Intraday "today" is defined in US/Eastern market timezone — the server validates session dates to ensure browser clock skew doesn't cause issues.

---

## Chart Types

Segmented toggle per panel: **[Candlestick | Area]** (default: Candlestick). Only one can be active.

- Candlestick: standard OHLC bars using lightweight-charts `CandlestickSeries`
- Area: close-price line with fill using lightweight-charts `AreaSeries`
- Both include a **volume histogram pane** below (separate `HistogramSeries`, scaled independently)

**Volume pane specification:**
- Height: 20% of main price pane
- Bar color: green when `close ≥ open`, red when `close < open`
- Shares the time axis with the price pane (zoom/pan synced)

---

## Panel Header

The top row of each panel shows symbol name, current price, and change:

```
AAPL  186.59  +9.31 (+5.01%)
```

| Field | Source |
|-------|--------|
| `last` | `close` from the most recent candle (or quote) |
| `change` | `close - previous_close` |
| `change_pct` | `(change / previous_close) * 100` |
| `previous_close` | **Intraday:** previous day's close from `daily_candles`. **Daily:** close of the day before the latest candle |

This data is **already fetched** from `GET /api/watchlists/{id}/quotes` (the watchlist quotes endpoint). `chart-panel.tsx` receives it as a prop from the parent, not from the `/candles` response. This avoids duplicate fetching.

For weekends/holidays, append a subtle timestamp: "as of 2026-04-17" when the latest candle is not from the current session.

---

## Stats Bar

Displayed between the symbol header and the timeframe switcher.

```
O 180.20   H 188.40   L 179.80   Vol 52.3M   52W 142.00 – 199.62
```

| Field | Source |
|-------|--------|
| Open | **Intraday:** first bar `open` of the session. **Daily:** `open` from the most recent `daily_candles` row |
| High | **Intraday:** max `high` across session bars. **Daily:** `high` from the most recent `daily_candles` row |
| Low | **Intraday:** min `low` across session bars. **Daily:** `low` from the most recent `daily_candles` row |
| Vol | **Intraday:** sum of `volume` across session bars. **Daily:** `volume` from the most recent `daily_candles` row |
| 52W High/Low | `week_52_high` / `week_52_low` from `realtime_quotes` (already fetched by the watchlist quotes endpoint when the group expanded) |

---

## API

### New endpoint

```
GET /api/stocks/{symbol}/candles
  ?resolution=5m|15m|1h|D
  &from=YYYY-MM-DD
  &to=YYYY-MM-DD
```

**Response (200 OK):**
```json
[
  { "time": "2026-04-16T09:30:00", "open": 180.20, "high": 188.40,
    "low": 179.80, "close": 186.59, "volume": 52300000 },
  ...
]
```

For intraday resolutions, `time` is an ISO datetime string. For daily, `time` is a date string. lightweight-charts accepts both formats natively.

**Empty response (200 OK, empty array):**
```json
[]
```
Returned when the symbol exists but no candles are available (e.g., no intraday data collected yet). Frontend shows "No data for {symbol}".

**Error responses:**
- `404 Not Found` — symbol does not exist in the `stocks` table
- `400 Bad Request` — invalid resolution (not `5m|15m|1h|D`), or date range exceeds maximum lookback, or `from > to`
- `500 Internal Server Error` — database or server error

**Server-side date range caps:**
| Resolution | Max range |
|-----------|-----------|
| 5m | 7 days |
| 15m | 30 days |
| 1h | 90 days |
| D | 2 years |

**Routing logic:**
- `resolution in (5m, 15m, 1h)` → query `intraday_candles` WHERE `stock_id = ? AND resolution = ? AND timestamp BETWEEN from AND to` ORDER BY `timestamp ASC`
- `resolution = D` → query `daily_candles` WHERE `stock_id = ? AND timestamp BETWEEN from AND to` ORDER BY `timestamp ASC`

**Auth:** no ownership check — candle data is not user-specific.

**No N+1:** single query per request, filtered by `stock_id` and time range.

**Data provider note:** This endpoint reads directly from PostgreSQL — it does NOT use the `DataProvider` abstraction. This is acceptable because it's a read path from our own database, not a fetch from the external MarketData.app API.

---

## Component Structure

```
frontend/src/pages/watchlists/
├── dashboard.tsx       ← existing; pass selectedSymbol to ChartPane
├── chart-pane.tsx      ← NEW: right pane shell, owns panelCount signal
└── chart-panel.tsx     ← NEW: single chart unit

frontend/src/lib/
├── stocks-api.ts       ← NEW: getCandles(symbol, resolution, from, to)
└── chart-utils.ts      ← NEW: timeframe → { from, to } date helpers

src/api/stocks/
├── __init__.py
├── routes.py           ← GET /{symbol}/candles
├── schemas.py          ← CandleResponse Pydantic schema
└── service.py          ← get_candles(symbol, resolution, from, to)
```

### State ownership

| Signal | Owner | Description |
|--------|-------|-------------|
| `selectedSymbol` | `dashboard.tsx` | Which stock is selected in the watchlist |
| `panelCount` | `chart-pane.tsx` | 1 or 2 panels |
| `resolution` | `chart-panel.tsx` (per instance) | Active timeframe per panel |
| `dailyRange` | `chart-panel.tsx` (per instance) | 1M / 3M / 1Y, only when resolution = D |
| candles data | `chart-panel.tsx` (per instance) | Fetched OHLCV array |

No global store. Solid signals, per-component.

---

## Loading and Error States

### Loading
When `selectedSymbol` changes or timeframe switches: show a skeleton placeholder in the chart area while the fetch is in flight. Do not flash a blank canvas.

**Loading skeleton visual spec:**
- Grey pulsing rectangle at chart canvas dimensions
- Minimum display time: 150ms to prevent flashes on cached/fast responses
- Shimmer effect on the stats bar fields (O/H/L/Vol)

### Chart lifecycle and cleanup
lightweight-charts maintains DOM and WebGL contexts until explicitly destroyed. To prevent memory leaks:

- `chart.remove()` in Solid's `onCleanup` for each panel instance
- `chart.applyOptions({ width, height })` via ResizeObserver on the container to handle window resize
- Each `chart-panel.tsx` instance owns its own lightweight-charts chart object

### Errors

| Condition | Display |
|-----------|---------|
| Symbol not found (404) | "No data for {symbol}" in panel body |
| Intraday data empty (market closed / no ticks yet) | "No intraday data — market may be closed. Switch to D." |
| Network / 5xx | "Failed to load chart — ↻ to retry" with retry button |

Each panel fails independently — one panel's error does not affect the other.

### Empty state (no symbol selected)
Right pane shows: "Select a stock from the watchlist to view its chart."

---

## Files Changed

| File | Action |
|------|--------|
| `frontend/src/pages/watchlists/dashboard.tsx` | Pass `selectedSymbol` to `ChartPane` |
| `frontend/src/pages/watchlists/chart-pane.tsx` | Create |
| `frontend/src/pages/watchlists/chart-panel.tsx` | Create |
| `frontend/src/lib/stocks-api.ts` | Create |
| `frontend/src/lib/chart-utils.ts` | Create |
| `src/api/stocks/__init__.py` | Create |
| `src/api/stocks/routes.py` | Create |
| `src/api/stocks/schemas.py` | Create |
| `src/api/stocks/service.py` | Create |
| `src/api/main.py` | Register stocks router |
| `frontend/package.json` | Add `lightweight-charts` dependency |
| `alembic/versions/xxx_add_intraday_res_index.py` | Create migration for `(stock_id, resolution, timestamp)` index |

---

## Test Plan

### Backend tests

**Unit tests** (`tests/unit/test_stocks_service.py`):
- Resolution routing: verify correct table choice (`intraday_candles` vs `daily_candles`) for each resolution
- Date range validation: verify max range caps are enforced, 400 on violation
- Resolution validation: verify 400 on invalid resolution string
- Timezone edge logic: verify "today" in ET offset is computed correctly

**Integration tests** (`tests/integration/test_stocks_routes.py`):
- Happy path: 5m, 15m, 1h, D resolutions return valid OHLCV data
- Date filtering: `from`/`to` params correctly filter results
- Empty set: new symbol with no intraday data returns `200 []`
- Unknown symbol: invalid ticker returns `404`
- Server-side validation: resolution enforces max range caps

### Frontend tests

**Component tests** (`frontend/src/pages/watchlists/chart-panel.test.tsx`):
- Timeframe switch: clicking 5m/15m/1H/D updates resolution and refetches
- Chart type toggle: candle ↔ area switch updates chart
- Loading state: skeleton displays during fetch
- Error states: 404, empty, network errors show appropriate messages
- Symbol change: changing `selectedSymbol` prop triggers refetch with preserved settings

**API client tests** (`frontend/src/lib/stocks-api.test.ts`):
- `getCandles()` constructs correct query params
- Error responses are surfaced correctly

---

## Database Migration

A new migration is required to add a composite index on `intraday_candles` for the hot query path:

```sql
-- Migration: add resolution to intraday_candles index
CREATE INDEX ix_intraday_candles_stock_res_ts
  ON intraday_candles(stock_id, resolution, timestamp);

-- Consider dropping the old index if no other query uses it:
-- DROP INDEX ix_intraday_candles_stock_ts;
```

This prevents Postgres from scanning 3× more rows than necessary (one per resolution) on every chart load.

---

## Out of Scope (v1)

- Different symbols per split panel — both panels always show `selectedSymbol`
- 3 or 4 panel grid
- Technical indicators (MA, RSI, MACD, Bollinger Bands)
- Drawing tools
- Persisting split state or chart type across page reload
- Draggable split divider (fixed 50/50 in v1)
- Log price scale toggle (default: linear)
- Mobile / touch layout
- Real-time streaming updates to the chart (deferred — WebSocket integration)
- Keyboard shortcuts (`D/5/1/H` for timeframe, `S` for split, `C/A` for chart type)
- Redis cache on `/candles` endpoint

---

## Design Review

This spec was reviewed on 2026-04-19 (reviewer: Opus 4.7). All blocking issues have been addressed:
- ✅ Intraday retention vs 1H default lookback collision resolved (1H → 5 days)
- ✅ Missing `resolution` in intraday index — migration added
- ✅ Test plan added with unit and integration test coverage
- ✅ Stats bar inconsistency resolved (header fields now documented)
- ✅ Multi-panel symbol change behavior documented
- ✅ Chart type toggle clarified as segmented control
- ✅ Panel 2 default timeframe improved (one step "up" from panel 1)
- ✅ Volume pane specification added (height 20%, color by candle direction)
- ✅ Chart cleanup lifecycle documented (`onCleanup`, ResizeObserver)
- ✅ Split panel height allocation specified (fixed 50/50)
- ✅ Server-side date range caps added (prevents runaway queries)
- ✅ Resolution validation specified (400 on invalid values)
- ✅ Data provider bypass documented as acceptable (read path from own DB)
