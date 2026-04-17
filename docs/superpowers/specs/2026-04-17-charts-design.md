# Charts Module — Design Spec

**Date:** 2026-04-17
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
- Panel 2 opens with the same symbol, defaulting to the next logical timeframe (if panel 1 is D → panel 2 defaults to 1H; otherwise defaults to D)
- Both panels always show `selectedSymbol` — independent symbol per panel is out of scope
- Unsplitting hides panel 2; panel 1 is unaffected
- Split state is **not** persisted across page reload (v1)

**Desktop-only.** Mobile layout deferred.

---

## Timeframe Switcher

Each panel has its own independent timeframe controls.

| Button | Resolution | Data source | Default lookback |
|--------|-----------|-------------|-----------------|
| 5m | 5m | `intraday_candles` | today |
| 15m | 15m | `intraday_candles` | last 5 trading days |
| 1H | 1h | `intraday_candles` | last 7 days |
| D | D | `daily_candles` | — |

When **D** is active, a secondary sub-selector appears inline:

| Sub-button | Lookback |
|-----------|---------|
| 1M | 30 calendar days |
| 3M | 90 calendar days (default) |
| 1Y | 365 calendar days |

Frontend computes `from` / `to` dates and passes them as query params. Intraday "today" is defined in US/Eastern market timezone — `chart-utils.ts` handles the offset so pre-market UTC hours don't cut to the wrong session date.

---

## Chart Types

Toggle per panel: **Candlestick** (default) / **Area**.

- Candlestick: standard OHLC bars using lightweight-charts `CandlestickSeries`
- Area: close-price line with fill using lightweight-charts `AreaSeries`
- Both include a **volume histogram** pane below (separate `HistogramSeries`, scaled independently)

---

## Stats Bar

Displayed between the symbol header and the timeframe switcher. Derived entirely from the candles array returned by the API — no second request.

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
  ?from=YYYY-MM-DD
  ?to=YYYY-MM-DD
```

**Response:**
```json
[
  { "time": "2026-04-16", "open": 180.20, "high": 188.40,
    "low": 179.80, "close": 186.59, "volume": 52300000 },
  ...
]
```

For intraday resolutions, `time` is an ISO datetime string (`2026-04-16T09:30:00`). For daily, `time` is a date string (`2026-04-16`). lightweight-charts accepts both formats natively.

**Routing logic:**
- `resolution in (5m, 15m, 1h)` → query `intraday_candles` WHERE `resolution = ?` AND `timestamp BETWEEN from AND to` ORDER BY `timestamp ASC`
- `resolution = D` → query `daily_candles` WHERE `timestamp BETWEEN from AND to` ORDER BY `timestamp ASC`

**Auth:** no ownership check — candle data is not user-specific. Validates that `symbol` exists in the `stocks` table; returns 404 if not found.

**No N+1:** single query per request, filtered by `stock_id` (resolved via symbol lookup) and time range.

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

---

## Out of Scope (v1)

- Different symbols per split panel — both panels always show `selectedSymbol`
- 3 or 4 panel grid
- Technical indicators (MA, RSI, MACD, Bollinger Bands)
- Drawing tools
- Persisting split state or chart type across page reload
- Mobile / touch layout
- Real-time streaming updates to the chart (deferred — WebSocket integration)
