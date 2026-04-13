# Scanner Control Panel — Design Spec

**Sub-project:** 3 of 6 (see `2026-04-08-frontend-roadmap.md`)
**Date:** 2026-04-13
**Status:** Approved

## 1. Purpose

Add a Scanner Control Panel at `/scanners` that surfaces EOD and pre-close scanner
results for review, and provides ephemeral on-demand intraday scanning. Bridges the
existing scanner backend to the UI and connects scanner output to watchlist creation.

## 2. Non-goals

- Scheduler UI for recurring intraday scans (sub-project 4)
- Charting within the scanner panel (sub-project 5)
- Per-ticker selection before saving (curation happens in the watchlist view after saving)
- Run history for intraday scans
- WebSocket progress streaming (scans are fast enough for synchronous execution)

## 3. Two-tab Layout

Route: `/scanners`

Two tabs share the same split-view shell (results list left, ticker detail right):

```
┌─────────────────────────────────────────────────────────────────┐
│  [EOD]  [Intraday]                                              │
├─────────────────────────────────────────────────────────────────┤
│  (tab content)                                                  │
└─────────────────────────────────────────────────────────────────┘
```

Tab switch resets results. Follows the existing `watchlist-view.tsx` split-view pattern.

## 4. EOD Tab

### Data source
Reads from existing `scanner_results` table — no new backend writes for this tab.
Requires a new `run_type` column on `scanner_results` (`eod` | `pre_close`).

### Controls

- **Scanner pills** — toggles for each registered scanner (Momentum, Price Action, Volume).
  Select one or many. Default: all selected.
- **Date/run dropdown** — shows last 5 trading days plus all runs for each day. Defaults
  to the latest run. Run entries are labeled by type and time:
  ```
  Apr 13 — Pre-close 15:45
  Apr 13 — EOD 16:15
  Apr 12 — EOD 16:15
  ```

### Results list (left panel)

When 2+ scanners selected, an **Overlap** section appears at the top listing tickers
that appeared in **every** selected scanner (intersection, not union). Below that,
each scanner's results are grouped under a header.

```
── Overlap (2) ──
AAPL   ●●  $189.20
NVDA   ●●  $872.10
── Momentum (8) ──
TSLA   ●   $172.30
── Price Action (6) ──
META   ●   $501.20
```

### Ticker detail (right panel)

Shows price, score, signal, volume, change %, sector, and which indicators fired
(sourced from `scanner_results.result_metadata`).

### Save as Watchlist

One-click button saves all visible results as a new watchlist. Auto-name:
`{Scanner(s)} — {RunType} {Date}` e.g. `Momentum + Price Action — Pre-close Apr 13`.
User can rename/delete tickers afterward in the watchlist view.

## 5. Pre-close Scanner (3:45 PM ET)

A second scheduled job runs at 3:45 PM ET Mon–Fri alongside the existing 4:15 PM EOD job.

**Differences from EOD:**
- Data source: `realtime_quotes` (today's open/high/low/last/volume = partial daily candle).
  `realtime_quotes` already stores this intraday summary — no new data fetching.
- `run_type = 'pre_close'` stored on results.
- Same scanner logic, same `scanner_results` table. No schema change beyond `run_type`.
- **Indicator compatibility:** Indicators that require a completed candle (e.g. confirmed
  close above MA) run on `last` price as a close proxy. Indicators requiring multiple
  historical bars (e.g. RSI) use prior `daily_candles` for history + today's `last` as
  the final data point. This is acceptable approximation for pre-close positioning intent.

**Purpose:** Identify stocks approaching a signal before close, enabling position entry
for tomorrow's open.

## 6. Intraday Tab

### Data source
Reads from `intraday_candles` (already populated). Timeframes: `15m`, `1h`.
(`5m` deferred until data pipeline populates it reliably.)

**Dependency note:** Intraday data fetching must be active for results to be meaningful.
The control panel works without it (returns empty results), but intraday scanners are
only useful once the pipeline runs.

### Controls

- **Scanner pills** — same toggle pattern as EOD tab
- **Timeframe dropdown** — `15m` | `1h`
- **Input scope dropdown** — `Full Universe` or any existing watchlist (fetched from
  `/api/watchlists`)
- **Run button** — triggers scan, shows spinner, results populate in-place

### Execution

Synchronous HTTP request to a new `/api/scanners/run` endpoint. No job queue, no
polling, no stored results. Results returned directly in the response payload.

### Results

Same split-view as EOD tab (overlap section, grouped results, ticker detail).
Results are ephemeral — cleared on tab switch or page navigation.

### Save as Watchlist

Same one-click behavior as EOD tab. This is the only persistence action available
in the intraday tab.

## 7. Backend Changes

### Schema

Add `run_type` column to `scanner_results`:
```sql
ALTER TABLE scanner_results ADD COLUMN run_type VARCHAR(20) DEFAULT 'eod';
```
Values: `eod`, `pre_close`. Existing rows default to `eod`.

### New Alembic migration

One migration for the `run_type` column addition.

### New APScheduler job

```python
# 3:45 PM ET Mon–Fri
scheduler.add_job(run_pre_close_scan, 'cron', day_of_week='mon-fri',
                  hour=15, minute=45, timezone='America/New_York')
```

### New scanner variant: `PreCloseScanner`

Subclasses existing scanner base. Data source swapped to `realtime_quotes` instead
of `daily_candles`. Scanner logic (indicator calculation) is unchanged.

### New API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/scanners` | List registered scanners with metadata (name, timeframe, description) |
| GET | `/api/scanners/results` | Query `scanner_results` with filters: scanner, run_type, date, limit |
| POST | `/api/scanners/run` | Trigger an intraday on-demand scan (returns results directly) |

## 8. Frontend Changes

### New files

```
frontend/src/pages/scanners/index.tsx          — route entry, tab switcher
frontend/src/pages/scanners/eod-tab.tsx        — EOD tab component
frontend/src/pages/scanners/intraday-tab.tsx   — Intraday tab component
frontend/src/pages/scanners/results-panel.tsx  — shared split-view (list + detail)
frontend/src/pages/scanners/ticker-detail.tsx  — right panel: ticker info + indicators
frontend/src/lib/scanners-api.ts               — API client for scanner endpoints
frontend/src/pages/scanners/types.ts           — TypeScript types
```

### Modified files

```
frontend/src/main.tsx      — add /scanners route
frontend/src/app.tsx       — add nav link
```

## 9. Testing

- **Unit:** Scanner API client, results grouping logic (overlap calculation), ticker detail rendering
- **Integration:** `/api/scanners/results` query filters, `/api/scanners/run` intraday execution
- **E2E:** EOD tab loads latest results; scanner pill toggle updates list; Save as Watchlist creates watchlist

## 10. Out of scope / future

- Intraday auto-scheduling (Scheduler UI, sub-project 4)
- Chart overlay of scan signals (Charting, sub-project 5)
- Alert creation from scanner results (Chart alerts, sub-project 6)
- `5m` timeframe (pending data pipeline)
- Scanner configuration UI (thresholds, parameters)
