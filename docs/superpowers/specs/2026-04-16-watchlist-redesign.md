# Watchlist Redesign — Design Spec

**Date:** 2026-04-16
**Sub-project:** Watchlist UI redesign (replaces existing dashboard + view components)

---

## Problem

The current watchlist UI is inert:
- `/watchlists` shows a category-grouped card grid (name + symbol count only)
- `/watchlists/:id` shows a static symbol list with a "chart placeholder"
- No prices, no inline add/remove, no usable interaction

The redesign brings it closer to TradingView's watchlist panel: collapsible groups, live/EOD prices per row, inline symbol management.

---

## Layout

The `/watchlists` route becomes a fixed two-pane layout.

```
/watchlists
┌─────────────────────────────────────────────────────┐
│ Nav: Dashboard | Watchlists | Scanners | Schedule   │
├───────────────────────┬─────────────────────────────┤
│ LEFT PANE (260px)     │ RIGHT PANE (flex)           │
│                       │                             │
│ ▼ SELL                │   Select a stock            │
│   GSAT  79.85  -0.04  │   to view detail            │
│   CVNA 358.55 -12.53  │                             │
│                       │                             │
│ ▶ BUY                 │                             │
│ ▶ OLD ACTIVE          │                             │
│                       │                             │
│ ▶ Scanner Results     │                             │
└───────────────────────┴─────────────────────────────┘
```

Right pane content is out of scope for this sub-project — shows a placeholder when a symbol is selected.

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

Response:
```json
[
  { "symbol": "GSAT", "last": 79.85, "chg": -0.04, "chg_pct": -0.05, "source": "realtime" },
  { "symbol": "CVNA", "last": 358.55, "chg": -12.53, "chg_pct": -3.38, "source": "eod" }
]
```

Backend logic in `WatchlistService.get_quotes()`:
1. For each symbol in the watchlist, check `realtime_quotes` for today's data (non-null `last`)
2. Fall back to the latest row in `daily_candles` if no realtime quote exists
3. `source` field is `"realtime"` or `"eod"` accordingly

**No polling.** Quotes load once when a group expands. Refresh on page reload. Live streaming is deferred to the charting sub-project.

---

## Interactions

### Expand/collapse groups
- Click category header to toggle
- Only one group expanded at a time
- Expanding triggers symbol + quote fetch for that watchlist if not yet cached

### Add symbol
```
▼ BUY                         [+]
  AAPL  186.59  +9.31  +5%
  DELL  186.59  +9.31  +5%
  ─────────────────────────────
  [TSLA__________] [Add]  [✕]
```
- `[+]` button in group header reveals inline input below symbol list
- Input auto-focuses on open
- `Add` → `POST /api/watchlists/{id}/symbols` → optimistic append, rollback on error
- `[✕]` or `Escape` closes input without action
- Invalid/unknown symbol shows inline error below input: `"TSLA not found"`

### Delete symbol
```
  AAPL  186.59  +9.31  +5%         ← normal state
  DELL  186.59  +9.31  +5%   [✕]   ← hover state
```
- Hover row reveals `✕` button on right
- Click `✕` → `DELETE /api/watchlists/{id}/symbols/{symbol}` → optimistic remove, restore on error

### Select symbol
- Click anywhere on a row (excluding `✕`) sets selected symbol
- Right pane updates in place with symbol name placeholder
- No navigation/route change

### Price indicator dots
```
●  = realtime quote (from realtime_quotes)
○  = EOD fallback (from daily_candles)
```

---

## Component Structure

```
frontend/src/pages/watchlists/
├── dashboard.tsx          ← route shell; owns left/right split + selectedSymbol state
├── watchlist-panel.tsx    ← left pane; renders all category groups
├── category-group.tsx     ← collapsible group; owns expand state + quote fetch
├── symbol-row.tsx         ← single row: dot, symbol, last, chg, chg%, hover ✕
└── types.ts               ← add QuoteResponse type

frontend/src/lib/
└── watchlists-api.ts      ← add getQuotes(watchlistId) method

src/api/watchlists/
├── routes.py              ← add GET /{id}/quotes route
├── schemas.py             ← add QuoteResponse Pydantic schema
└── service.py             ← add get_quotes(watchlist_id, user_id) method
```

### State ownership
- `dashboard.tsx` owns: `selectedSymbol`, `expandedId` (which group is open)
- `category-group.tsx` owns: its quote data (fetched on expand, cached locally)
- No global store needed

### Files untouched
- `edit-modal.tsx` — still used for renaming watchlists
- `create-modal.tsx` — still used for creating watchlists
- `watchlist-view.tsx` — **deleted** (replaced by new components)

---

## Files Changed Summary

| File | Action |
|------|--------|
| `frontend/src/pages/watchlists/dashboard.tsx` | Rewrite |
| `frontend/src/pages/watchlists/watchlist-view.tsx` | Delete |
| `frontend/src/pages/watchlists/watchlist-panel.tsx` | Create |
| `frontend/src/pages/watchlists/category-group.tsx` | Create |
| `frontend/src/pages/watchlists/symbol-row.tsx` | Create |
| `frontend/src/main.tsx` | Remove `/watchlists/:id` route |
| `frontend/src/pages/watchlists/types.ts` | Add `QuoteResponse` |
| `frontend/src/lib/watchlists-api.ts` | Add `getQuotes()` |
| `src/api/watchlists/routes.py` | Add `GET /{id}/quotes` |
| `src/api/watchlists/schemas.py` | Add `QuoteResponse` |
| `src/api/watchlists/service.py` | Add `get_quotes()` |

---

## Out of Scope

- Right pane content (what to show on symbol selection) — next discussion
- Live price streaming / WebSocket updates — charting sub-project
- Watchlist create/rename/delete management UI — unchanged
- Moving symbols between watchlists
