# Watchlist Redesign — Design Spec

**Date:** 2026-04-16
**Sub-project:** Watchlist UI redesign (replaces existing dashboard + view components)
**Review:** Opus 4.6 code review applied 2026-04-16

---

## Problem

The current watchlist UI is inert:
- `/watchlists` shows a category-grouped card grid (name + symbol count only)
- `/watchlists/:id` shows a static symbol list with a "chart placeholder"
- No prices, no inline add/remove, no usable interaction

The redesign brings it closer to TradingView's watchlist panel: collapsible groups, live/EOD prices per row, inline symbol management.

---

## Layout

The `/watchlists` route becomes a fixed two-pane layout. The `/watchlists/:id` route is removed.

```
/watchlists
┌─────────────────────────────────────────────────────┐
│ Nav: Dashboard | Watchlists | Scanners | Schedule   │
├───────────────────────┬─────────────────────────────┤
│ LEFT PANE (260px)     │ RIGHT PANE (flex)           │
│                       │                             │
│ ▼ SELL           [↻]  │   Select a stock            │
│   ● GSAT  79.85 -0.04 │   to view detail            │
│   ○ CVNA 358.55-12.53 │                             │
│                       │                             │
│ ▼ BUY            [↻]  │                             │
│   ● AAPL 186.59  +9.31│                             │
│                       │                             │
│ ▶ OLD ACTIVE          │                             │
│ ▶ Scanner Results     │                             │
│   ▶ Price Action      │  ← individual auto-watchlists│
│   ▶ Momentum          │    under the category       │
└───────────────────────┴─────────────────────────────┘
```

Multiple groups can be expanded simultaneously. Right pane shows a placeholder until charting is implemented.

**Desktop-only.** Mobile layout is deferred.

---

## Data & Price Fetching

### Existing endpoints (unchanged)
- `GET /api/watchlists` — all categories + watchlists (used on mount)
- `GET /api/watchlists/{id}/symbols` — symbol list for a watchlist
- `POST /api/watchlists/{id}/symbols` — add symbol
- `DELETE /api/watchlists/{id}/symbols/{symbol}` — remove symbol

### New endpoint
```
GET /api/watchlists/{id}/quotes
```

**Ownership check:** Returns 404 if the watchlist doesn't exist or isn't owned by the authenticated user. Uses the same `service.get_watchlist(watchlist_id, user_id)` guard as all other routes.

Response:
```json
[
  { "symbol": "GSAT", "last": 79.85, "change": -0.04, "change_pct": -0.05, "source": "realtime" },
  { "symbol": "CVNA", "last": 358.55, "change": -12.53, "change_pct": -3.38, "source": "eod" }
]
```

Field names match the DB model (`change`, `change_pct` — not abbreviated).

### Backend query strategy (no N+1)

`WatchlistService.get_quotes(watchlist_id, user_id)` uses two batch queries, not per-symbol lookups:

1. **Realtime query:** one query with a window function (`ROW_NUMBER() OVER (PARTITION BY stock_id ORDER BY timestamp DESC)`) over `realtime_quotes` filtered to today's date. Returns the latest realtime row per stock in the watchlist.
2. **EOD fallback query:** same window function over `daily_candles`, fetching the latest **two** rows per stock (to compute day change: `close[0] - close[1]`). Runs only for symbols not covered by step 1.
3. **Merge in Python:** combine both result sets into the final list.

For EOD rows: `change = latest_close - prev_close`, `change_pct = change / prev_close * 100`. If only one candle row exists (new listing), `change = null`, `change_pct = null` — frontend renders "—".

### Price indicator dots

```
●  green dot  = realtime quote (from realtime_quotes, today)
○  grey dot   = EOD fallback (from daily_candles)
```

Each dot has a hover tooltip: `"Realtime"` or `"End of day (YYYY-MM-DD)"`.

### No polling

Quotes load once when a group expands. Manual refresh via ↻ button in group header. Live streaming deferred to the charting sub-project.

---

## Interactions

### Expand/collapse groups

- Click category header to toggle — **multiple groups can be expanded simultaneously**
- Expansion state persisted in `localStorage` (key: `watchlist-expanded-ids`) so it survives page reload
- On expand: fetch symbols (`GET /symbols`) and quotes (`GET /quotes`) in parallel
- On collapse: state retained in memory (re-expand is instant)

### Loading and error states within a group

**On expand — first paint:**
- Symbol names render immediately when `/symbols` resolves
- Price cells (`last`, `change`, `change_pct`) show skeleton placeholders until `/quotes` resolves
- If `/quotes` fails: render rows without prices, show an inline banner: `"Prices unavailable — ↻ to retry"`. Does not block add/remove interactions.

```
▼ SELL                              [↻]
  ● GSAT   79.85   ████   ████          ← skeleton while quotes load
  ● CVNA  358.55  -12.53  -3.38%        ← resolved
  ── Prices unavailable — ↻ to retry ── ← on failure
```

### Refresh

Each expanded group header has a `↻` button. Clicking it re-fetches `/quotes` for that group only (not `/symbols`). Shows a spinner while loading.

### Add symbol (click + to reveal)

```
▼ BUY                                    [+]
  ● AAPL   186.59   +9.31   +5.01%
  ● DELL   186.59   +9.31   +5.25%
  ──────────────────────────────────────────
  [TSLA__________] [Add]  [✕]
```

- `[+]` button in group header reveals inline input below symbol list
- Input auto-focuses on open
- `Add` → `POST /api/watchlists/{id}/symbols`:
  - On success: append row optimistically with skeleton price cells, then re-fetch `/quotes` for the group to populate prices
  - On 404 (symbol not found): show inline error below input: `"TSLA not found"`
  - On 400 (already exists): show inline error: `"TSLA already in this list"`
  - On network error / 5xx: show inline error: `"Failed to add — try again"`
- `[✕]` or `Escape` closes input without action

### Delete symbol (hover reveals ✕)

```
  AAPL   186.59   +9.31   +5.01%         ← normal state
  DELL   186.59   +9.31   +5.25%   [✕]   ← hover state
```

- Hover row reveals `✕` button on right edge
- Click `✕` → `DELETE /api/watchlists/{id}/symbols/{symbol}`:
  - Optimistic remove: row disappears immediately
  - On error: row restored at its **original index** (by `priority` order), inline toast: `"Failed to remove DELL"`

### Select symbol

- Click anywhere on a row (excluding `✕`) sets `selectedSymbol` in `dashboard.tsx`
- Right pane updates in place with symbol name placeholder
- No navigation / route change

**Edge cases:**
- User deletes the currently-selected symbol → clear `selectedSymbol` (right pane returns to empty state)
- User collapses the group containing the selected symbol → keep `selectedSymbol` (right pane stays showing it)
- User deletes the watchlist containing the selected symbol → out of scope (watchlist delete is outside this spec)

---

## Scanner Results Category

"Scanner Results" is a **category** containing multiple auto-generated watchlists (e.g. "Price Action", "Momentum"). It renders like any other category — a collapsible group per watchlist, not a single entry. The ASCII mock label `▶ Scanner Results` refers to the category header, which expands to show its individual watchlists as sub-groups.

---

## Component Structure

```
frontend/src/pages/watchlists/
├── dashboard.tsx          ← route shell; owns left/right split, selectedSymbol
├── watchlist-panel.tsx    ← left pane; renders all category groups
├── category-group.tsx     ← collapsible group; owns expand state + quote fetch
├── symbol-row.tsx         ← single row: dot, symbol, last, change, change_pct, hover ✕
└── types.ts               ← add QuoteResponse type

frontend/src/lib/
└── watchlists-api.ts      ← add getQuotes(watchlistId) method

src/api/watchlists/
├── routes.py              ← add GET /{id}/quotes route
├── schemas.py             ← add QuoteResponse Pydantic schema
└── service.py             ← add get_quotes(watchlist_id, user_id) — batch queries
```

### State ownership

- `dashboard.tsx` owns: `selectedSymbol`, nothing else
- `watchlist-panel.tsx` owns: category/watchlist list (from `GET /api/watchlists`)
- `category-group.tsx` owns: expanded state, symbols, quotes, add-input visibility
- Expansion set persisted to `localStorage` (read on mount, written on toggle)
- No global store needed

### Files untouched
- `edit-modal.tsx` — still used for renaming watchlists
- `create-modal.tsx` — still used for creating watchlists

---

## Files Changed Summary

| File | Action |
|------|--------|
| `frontend/src/main.tsx` | Remove `/watchlists/:id` route |
| `frontend/src/pages/watchlists/dashboard.tsx` | Rewrite |
| `frontend/src/pages/watchlists/watchlist-view.tsx` | Delete |
| `frontend/src/pages/watchlists/watchlist-panel.tsx` | Create |
| `frontend/src/pages/watchlists/category-group.tsx` | Create |
| `frontend/src/pages/watchlists/symbol-row.tsx` | Create |
| `frontend/src/pages/watchlists/types.ts` | Add `QuoteResponse` |
| `frontend/src/lib/watchlists-api.ts` | Add `getQuotes()` |
| `src/api/watchlists/routes.py` | Add `GET /{id}/quotes` |
| `src/api/watchlists/schemas.py` | Add `QuoteResponse` Pydantic schema |
| `src/api/watchlists/service.py` | Add `get_quotes()` with batch queries |

---

## Out of Scope

- Right pane content (what to show on symbol selection) — next discussion
- Live price streaming / WebSocket updates — charting sub-project
- Watchlist create/rename/delete management UI — unchanged
- Moving symbols between watchlists
- Mobile / touch layout — desktop-only for now
- Keyboard navigation (↑/↓ rows, Enter to select, `/` to focus add input) — deferred
- Virtualization — revisit if any watchlist exceeds ~200 symbols
