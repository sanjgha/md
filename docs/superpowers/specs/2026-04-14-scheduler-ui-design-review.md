# Review — Scheduler UI Design Spec

**Reviewer:** Claude (Opus 4.6)
**Date:** 2026-04-14
**Subject:** `2026-04-14-scheduler-ui-design.md`
**Verdict:** Approve with revisions — spec is coherent and well-scoped, but several
load-bearing details are under-specified and one architectural choice needs a second look.

---

## Summary

The spec lands the right scope for sub-project 4: two job cards, a history table,
three routes, one new table. It reuses `PreCloseExecutor` and `scanner_results` rather
than inventing parallel state, which is the right call. The issues below are mostly
gaps (timezone, DOW, concurrency, auth) rather than mis-design.

---

## Blocking issues

### B1. Timezone is missing from `schedule_config`
The existing `create_eod_scheduler` pins `America/New_York` (`src/data_fetcher/scheduler.py:12`).
The spec stores `hour`/`minute` as bare integers with no timezone. If the FastAPI
container runs in UTC (OCI default), a user entering `16:15` will schedule 16:15 UTC —
three–four hours early depending on DST.

**Fix:** either hardcode `America/New_York` in `schedule_manager.start()` (document it
in §5), or add a `timezone TEXT NOT NULL DEFAULT 'America/New_York'` column. Hardcoding
is fine for now but must be explicit in the spec.

### B2. Day-of-week is not configurable and not stored
The existing scheduler runs Mon–Fri. The spec's UI shows "⏰ Mon–Fri" as a static label
but `schedule_config` has no `day_of_week` column. This is probably intentional
(trading days only) but needs to be stated: **the cron trigger will hardcode
`day_of_week="mon-fri"` and the UI label is decorative**. Otherwise a future reader
will assume the schedule is user-configurable.

### B3. "Run Now" synchronous call will block the request thread
EOD scans over 500 tickers are not instant. The spec has `POST /run` return
`{ "status": "ok", "result_count": 47 }` synchronously. If the scan takes 30–60 seconds:
- The HTTP request will hit proxy/client timeouts on slower runs.
- A second Run Now (or a scheduled fire during a manual run) will double-execute.

**Fix:** pick one and document it.
- (a) Run the job in a thread via APScheduler's `scheduler.add_job(..., next_run_time=now)`
  and return `202 Accepted` with a job id; frontend polls `GET /jobs` for updated `last_run`.
- (b) Keep synchronous but add an in-process lock per `job_id` and document the expected
  max latency budget.

Related: the spec says "Button shows a spinner while running" — that only works if the
request actually stays open, which contradicts (a). Pick a model.

### B4. Auth / who can trigger these routes?
Every other router in `src/api/main.py` is behind `SessionMiddleware`. The spec doesn't
say whether `/api/schedule/*` routes require auth. Given Run Now can kick off a 500-ticker
data pull, this must be authenticated. **Add a line to §6:** "All routes require an
authenticated session; mounted under the same middleware stack as `/api/watchlists`."

---

## Should-fix

### S1. `BackgroundScheduler` + uvicorn workers
If the app is ever started with `--workers N > 1`, every worker will boot its own
`BackgroundScheduler` from `lifespan`, and the job will fire N times. APScheduler has
no built-in distributed locking against the app DB.

**Fix:** either (a) document "must run with a single worker" in §5, or (b) use a
jobstore-backed scheduler (`SQLAlchemyJobStore`) with `coalesce=True` + a DB advisory
lock. (a) is acceptable for now — just call it out.

### S2. "Skipped" vs "Done" — how is it recorded?
§3 run history shows `Skipped` when a job "produced zero results (not a failure)." But
`scanner_results` only stores rows *when* a ticker matches. A zero-result run writes
nothing, so there's no row to render as "Skipped" either. The table would just show
the previous day's runs.

**Fix:** either
- Add a `scanner_runs` audit table (job_id, ran_at, status, result_count), or
- Document that history is inferred from `scanner_results` aggregation and zero-result
  runs simply don't appear (drop "Skipped" from the UI).

The current spec implies the first but doesn't define the schema. Pick one.

### S3. Auto-save watchlist naming collision
`EOD Scan — Apr 14` is not unique if a user runs EOD twice (scheduled + Run Now with
auto-save on). Watchlists table likely has a uniqueness constraint on name. Either:
- Append a time suffix (`EOD Scan — Apr 14 16:15`), or
- Overwrite/append to the existing watchlist for that date, or
- Document the expected behavior on collision.

### S4. PATCH validation
Spec says all fields are optional. Missing:
- `hour` bounds (0–23), `minute` bounds (0–59) — what's the error shape?
- What happens if you PATCH `enabled=false` mid-run? (Almost certainly: let the running
  job finish, don't fire next one. State that.)
- Atomicity: PATCH updates both DB and the live scheduler. If the DB write succeeds and
  `scheduler.reschedule_job` raises, state drifts. Wrap in a try/rollback or note
  that the lifespan resync on next startup is the recovery path.

### S5. `updated_at` not auto-updated
Schema defines `updated_at TIMESTAMP NOT NULL DEFAULT now()` but nothing updates it on
PATCH. Either add `ON UPDATE` (Postgres needs a trigger) or have the app write
`datetime.utcnow()` on every update. Low priority but easy to miss.

---

## Nice-to-have

### N1. Frontend realtime refresh
When a scheduled job fires (or another tab runs it), the current `/schedule` view
won't know. The app already has a WebSocket layer (`src/api/ws.py`). Consider
publishing a `schedule.run_completed` event so open tabs refresh `last_run` and the
history table. Out of scope is fine, but worth mentioning in §9.

### N2. History table scope
"Last 7 days" is reasonable but §3 doesn't say whether rows are paginated, sorted
(desc by ran_at presumably), or filterable by job. Specify sort order at minimum.

### N3. Time input UX on mobile
`<input type="time">` behavior varies wildly across mobile browsers (12h vs 24h, AM/PM
toggle). Not a blocker — call out that desktop is the primary target.

### N4. Testing — add scheduler interaction
§8 covers API + UI but doesn't test the scheduler integration itself: reschedule
actually changes the next fire time, pause stops the trigger, resume restores it.
Add one integration test that constructs a `BackgroundScheduler`, calls
`schedule_manager.reschedule(...)`, and asserts `scheduler.get_job(...).next_run_time`.

### N5. CLI scheduler parity
§5 correctly says the CLI `schedule-scan` / `schedule-pre-close` are unchanged.
But now the CLI reads hardcoded times while the UI reads `schedule_config`. Users
editing in the UI will get confused when the CLI ignores their settings. Either:
- Have the CLI also read `schedule_config`, or
- Add a note to the CLI help output that the API-based scheduler is authoritative.

Worth a line in §9 at minimum.

---

## Things the spec got right

- Reusing `PreCloseExecutor` and the EOD callable as-is — good separation.
- Keeping scheduler state in one table keyed by `job_id` — simple and adequate.
- Not shipping notifications / per-scanner config / intraday scheduling in v1.
- PATCH returning partial updates rather than full replace.
- History reads from `scanner_results` — no duplicate state (modulo S2).

---

## Recommended next step

Address B1–B4 inline in the spec (they're short — timezone, DOW hardcode statement,
Run Now execution model, auth note). S1–S5 can be deferred to the implementation plan
as open questions to resolve during `/write-plan`.
