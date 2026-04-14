# Scheduler UI — Design Spec

**Sub-project:** 4 of 6 (see `2026-04-08-frontend-roadmap.md`)
**Date:** 2026-04-14
**Status:** Approved

## 1. Purpose

Add a `/schedule` page that gives the user visibility into scheduled scanner jobs
(EOD and pre-close) and control over their timing, enable/disable state, auto-save
behaviour, and on-demand execution. Bridges the existing APScheduler backend to the UI.

## 2. Non-goals

- Scheduling intraday scans (those are on-demand from the Scanner panel)
- Per-scanner configuration (which indicators fire, thresholds)
- Charting of scan results (sub-project 5)
- Email / push notifications on job completion

## 3. UI — `/schedule` route

New nav link: **Watchlists | Scanners | Schedule**

### Job cards

Two cards, one per scheduled job:

```
┌─ EOD Scan ──────────────────────────────────────────────────┐
│  ⏰ Mon–Fri   Last run: Apr 13 16:15  ✓ 47 tickers          │
│  Time: [16:15]   Auto-save: [○ off]   [▶ Run Now]  [●──]   │
└─────────────────────────────────────────────────────────────┘
┌─ Pre-close Scan ────────────────────────────────────────────┐
│  ⏰ Mon–Fri   Last run: Apr 13 15:45  ✓ 31 tickers          │
│  Time: [15:45]   Auto-save: [○ off]   [▶ Run Now]  [●──]   │
└─────────────────────────────────────────────────────────────┘
```

**Time field** — inline edit. Click the time to activate an `<input type="time">`.
Blur or Enter commits the change via PATCH. Invalid times show an inline error.

**Auto-save toggle** — off by default. When enabled, a watchlist is automatically
created after each run, named `{Job} — {Date}` e.g. `EOD Scan — Apr 14`. User can
rename or delete it from the Watchlists view. The toggle persists in `schedule_config`.

**Run Now** — triggers the job immediately via POST. Button shows a spinner while
running, then shows inline result: `✓ 47 tickers` or `✗ Failed`. No redirect.

**Enable toggle** — pauses or resumes the scheduled job. On = job fires at scheduled
time. Off = job is registered but will not fire automatically.

### Run history table

Reads from existing `scanner_results` table. Shows last 7 days.

```
┌──────────────┬───────────────┬──────────┬───────────┐
│ Job          │ Ran At        │ Results  │ Status    │
├──────────────┼───────────────┼──────────┼───────────┤
│ EOD Scan     │ Apr 13 16:15  │ 47       │ ✓ Done    │
│ Pre-close    │ Apr 13 15:45  │ 31       │ ✓ Done    │
│ EOD Scan     │ Apr 12 16:15  │ 52       │ ✓ Done    │
│ Pre-close    │ Apr 12 15:45  │ —        │ Skipped   │
└──────────────┴───────────────┴──────────┴───────────┘
```

"Skipped" appears when a job was enabled but produced zero results (not a failure).

### First-time / empty state

Cards display default times from `schedule_config` seed data. Both enable toggles on,
both auto-save toggles off. History table shows: *"No runs yet. Jobs will appear here
after their first execution."*

## 4. Backend — DB

### New table: `schedule_config`

```sql
CREATE TABLE schedule_config (
    job_id      TEXT PRIMARY KEY,   -- "eod_scan" | "pre_close_scan"
    hour        INTEGER NOT NULL,
    minute      INTEGER NOT NULL,
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    auto_save   BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at  TIMESTAMP NOT NULL DEFAULT now()
);
```

Seeded via Alembic migration with two rows:

| job_id | hour | minute | enabled | auto_save |
|---|---|---|---|---|
| eod_scan | 16 | 15 | true | false |
| pre_close_scan | 15 | 45 | true | false |

### Alembic migration

One migration: create `schedule_config` table + seed rows.

## 5. Backend — Scheduler

The existing `BlockingScheduler` in `src/data_fetcher/scheduler.py` and the separate
CLI scheduler commands (`schedule-scan`, `schedule-pre-close`) are **unchanged**.

A new `BackgroundScheduler` is started inside the FastAPI app's `lifespan` handler
(alongside the existing API server process). On startup it:

1. Reads both rows from `schedule_config`
2. Registers `eod_scan` and `pre_close_scan` jobs using `CronTrigger`
3. Respects `enabled` — pauses job immediately if `enabled=False`

The `PreCloseExecutor` and EOD scanner callable are reused unchanged as job callbacks.

When auto_save is enabled, the job callback creates a watchlist via the existing
watchlist service after a successful run.

### Module: `src/api/schedule_manager.py`

Owns the `BackgroundScheduler` instance and exposes:

```python
def start(db_session) -> None          # called from lifespan on startup
def stop() -> None                     # called from lifespan on shutdown
def reschedule(job_id, hour, minute)   # called by PATCH route
def pause(job_id) / resume(job_id)     # called by PATCH route
def run_now(job_id) -> int             # returns result_count; called by POST route
```

## 6. Backend — API routes

New router: `src/api/routes/schedule.py`

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/schedule/jobs` | Return both jobs: config + last run info |
| PATCH | `/api/schedule/jobs/{job_id}` | Update hour/minute/enabled/auto_save |
| POST | `/api/schedule/jobs/{job_id}/run` | Trigger immediately, return result count |

### GET `/api/schedule/jobs` response

```json
[
  {
    "job_id": "eod_scan",
    "name": "EOD Scan",
    "hour": 16,
    "minute": 15,
    "enabled": true,
    "auto_save": false,
    "last_run": { "ran_at": "2026-04-13T16:15:00", "result_count": 47 }
  },
  ...
]
```

`last_run` is `null` if no runs exist yet.

### PATCH `/api/schedule/jobs/{job_id}` request

All fields optional (partial update):
```json
{ "hour": 16, "minute": 30, "enabled": true, "auto_save": true }
```

### POST `/api/schedule/jobs/{job_id}/run` response

```json
{ "status": "ok", "result_count": 47 }
```

Or on error: `{ "status": "error", "detail": "..." }`

## 7. Frontend

### New files

```
frontend/src/pages/schedule/index.tsx      — route entry, renders job cards + history
frontend/src/pages/schedule/job-card.tsx   — single job card (time edit, toggles, run now)
frontend/src/lib/schedule-api.ts           — API client for schedule endpoints
frontend/src/pages/schedule/types.ts       — TypeScript types
```

### Modified files

```
frontend/src/main.tsx    — add /schedule route
frontend/src/app.tsx     — add Schedule nav link
```

## 8. Testing

- **Unit:** `schedule-api.ts` client, `job-card.tsx` inline time edit and toggle states
- **Integration:** GET returns seeded defaults; PATCH updates DB + verifies live reschedule;
  POST /run returns result count
- **E2E:** Schedule page loads with two cards; time edit commits on blur; Run Now shows
  inline result; history table populates after a run

## 9. Out of scope / future

- Intraday auto-scheduling
- Notification on job completion (email, push)
- Per-scanner selection for scheduled runs
- Smart Collections (Watchlist phase 2) — scanner signal lifecycle tracking
