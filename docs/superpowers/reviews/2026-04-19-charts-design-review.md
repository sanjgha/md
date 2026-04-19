# Charts Module Design Review

**Date:** 2026-04-19
**Reviewer:** Claude (Opus 4.7)
**Spec:** `2026-04-17-charts-design.md`
**Supersedes:** `2026-04-17-charts-design-review.md` (expands + corrects prior review)

---

## TL;DR

Design is pragmatic and well-scoped. Two items are **blocking**: (1) the intraday retention window (7 days) collides with the 1H "last 7 days" default, and (2) the `intraday_candles` index does not include `resolution`, which will slow the hottest query path in production. Several smaller gaps — Stats Bar inconsistency, ambiguous symbol-change behaviour across panels, missing test plan — should be resolved before coding.

---

## Blocking Issues

### B1. Intraday retention vs. 1H default lookback

`IntradayCandle` has **7-day retention** (see `src/db/models.py:83`). The spec's 1H default lookback is also "last 7 days" — meaning after an EOD cleanup run, the earliest bar in a 1H view will drop off the left edge of the chart by a full day. A user switching from D→1H on a Friday afternoon may see the chart start on *Tuesday* rather than the full trading week.

**Fix:** pick one:
- Reduce the 1H default to "last 5 trading days" (consistent with 15m default)
- Extend intraday retention to 10 days in the retention job, giving a safety buffer

### B2. Missing `resolution` in the intraday query index

The spec's routing logic filters intraday candles by `(stock_id, resolution, timestamp)`. The existing index `ix_intraday_candles_stock_ts` is on `(stock_id, timestamp)` only (`src/db/models.py:106`). With three resolutions per stock, Postgres will use the stock prefix then filter, scanning ~3× more rows than necessary on every chart load.

**Fix:** add a migration alongside this work:
```sql
CREATE INDEX ix_intraday_candles_stock_res_ts
  ON intraday_candles(stock_id, resolution, timestamp);
-- Consider dropping ix_intraday_candles_stock_ts if no other query needs it.
```

### B3. Test plan is absent

CLAUDE.md mandates TDD, and integration tests use testcontainers against real Postgres. The spec lists no test cases. At minimum the "Files Changed" section should name:
- `tests/unit/test_stocks_service.py` — routing between `intraday_candles` / `daily_candles` by resolution, timezone edge logic
- `tests/integration/test_stocks_routes.py` — 404 on unknown symbol, empty intraday set, 5m/15m/1h/D happy paths, date-range filtering
- Frontend component tests for `chart-panel.tsx` (timeframe switch, error states)

---

## Design Inconsistencies

### D1. Stats Bar omits the header fields from the mock

The Layout mock shows the panel header line as:
```
AAPL  186.59  +9.31 (+5.01%)
```
…but the Stats Bar table documents only `O / H / L / Vol / 52W`. Where do `last`, `change`, `change_pct` come from? They aren't in the `/candles` response schema. Three options — pick one and document it:
1. Derive from the last candle in the array (intraday close of most recent bar; daily close of latest row). Need a prev-close to compute `change`.
2. Reuse the quote already fetched by `/api/watchlists/{id}/quotes` (parent state).
3. Add `previous_close` to the candles response.

Option 2 is cheapest and consistent with the redesign spec.

### D2. Symbol change behaviour when split is active

Both panels share `selectedSymbol` (from `dashboard.tsx`). When the user clicks a different stock in the left pane:
- Do **both** panels refetch? (implied — and each uses its own resolution)
- Do timeframe/chart-type/dailyRange per-panel settings persist across symbol changes, or reset?

Spec doesn't say. Power users will want settings to persist (compare two symbols at the same multi-timeframe layout). Document the intended behaviour.

### D3. `[C][A]` — two buttons or a toggle?

The mock shows `[C][A]` as two bracketed items (like a segmented control) but reads naturally as "C=Candlestick, A=Area". Clarify whether this is a segmented toggle (one active) or two separate buttons. The rest of the spec treats chart type as a single toggle; align the mock.

### D4. Panel 2 default timeframe logic is thin

> "if panel 1 is D → panel 2 defaults to 1H; otherwise defaults to D"

So if panel 1 is 5m, panel 2 is D — skipping 15m/1H. The stated workflow (EOD review → intraday timing) suggests a more useful default: **panel 2 = one step "up" from panel 1** (5m→1H, 15m→1H, 1H→D, D→1H). Cheap change, better UX.

---

## Missing Items

### M1. Stats Bar for "market closed" days

On weekends / holidays the stats bar pulls Open/High/Low/Vol from "the most recent `daily_candles` row" — which is Friday. Fine, but add a subtle timestamp ("as of 2026-04-17") so the user isn't confused when looking at the chart on a Sunday.

### M2. Volume pane specification

Spec says "volume histogram pane below" but doesn't define:
- Relative height (typical: 20-25% of main pane)
- Bar colour convention (green = close ≥ open, red = close < open)
- Whether it shares the time axis with the price pane (it should)

### M3. Chart cleanup on unmount and on resize

lightweight-charts keeps DOM + WebGL contexts alive until explicitly destroyed. With timeframe switching plus split toggle, instances can leak. Add to the spec:
- `chart.remove()` in Solid's `onCleanup`
- `chart.applyOptions({ width, height })` via ResizeObserver on the container

Not critical for correctness but likely to surface as a memory-growth bug in a long session.

### M4. Split panel height allocation

When `panelCount = 2`, how is vertical space divided? 50/50 implied. Is it resizable (draggable divider)? If not, say so explicitly — users *will* ask.

### M5. Watchlist → Stocks table coupling

Endpoint returns 404 if `symbol` is not in `stocks`. But a user could add *any* symbol to a watchlist via the existing `POST /api/watchlists/{id}/symbols` — the watchlist flow doesn't require the symbol to exist in `stocks`. Result: a legitimate watchlist row produces a 404 chart. Either (a) enforce `stocks` membership on watchlist insert, or (b) make the chart endpoint return `200 []` with a clearer "no data collected yet" UI state, distinct from true 404.

### M6. Loading skeleton visual spec

"Show a skeleton placeholder" — define it:
- Grey pulsing rectangle at chart dimensions? Shimmer bars approximating candles? Spinner only?
- Minimum display time (e.g., 150ms) to prevent flashes on cached data

---

## Smaller Nits

- **Timezone helper location.** `chart-utils.ts` handling ET offset is client-side, which means the browser's clock skew affects "today". Safer to have the server compute "today" for intraday and return it in the response meta, or accept `session_date` from client with server validation.
- **Max range guard.** `from`/`to` is unbounded. A malformed/manual request for `resolution=5m` and a 1-year span could return ~20K rows per stock. Add a server-side cap (e.g., 5m ≤ 7 days, 15m ≤ 30 days, 1h ≤ 90 days, D ≤ 2 years) and 400 on violation.
- **Daily 1Y lookback at retention boundary.** Daily retention is 1 year; 1Y lookback will miss the oldest day on the first refresh after cleanup. Same fix pattern as B1 — either extend retention buffer or shorten lookback to 360 days.
- **Price scale mode.** Log vs linear not specified. Default linear is fine, but for 1Y daily of a high-mover stock, log is more informative. Out-of-scope note is acceptable.
- **Resolution string contract.** DB stores `resolution` as `String(10)` with no enum constraint. Frontend/backend must agree on exactly `5m | 15m | 1h | D` (lowercase `h`, uppercase `D`) and the service must reject anything else with 400, not silently return empty.

---

## Consistency Check vs Architecture

| Concern | Status | Note |
|---|---|---|
| Uses existing SQLAlchemy models | ✅ | `intraday_candles`, `daily_candles` |
| DataProvider abstraction bypassed | ⚠️ | Acceptable — this is a *read* path from our DB, not a fetch from MarketData.app. Document that in the spec. |
| Per-panel independent error handling | ✅ | Good |
| TDD / test plan | ❌ | See B3 |
| Conventional-commits discipline | N/A | Spec-level; applies at commit time |
| Migration present for new indexes | ❌ | See B2 |

---

## Recommended Actions

### Before implementation (blockers)
1. Reconcile intraday retention vs. 1H default lookback (B1)
2. Add migration for `(stock_id, resolution, timestamp)` index (B2)
3. Add a Test Plan section to the spec (B3)
4. Clarify Stats Bar `last/change/change_pct` source (D1)
5. Document multi-panel symbol-change behaviour (D2)

### During implementation
6. Server-side date range caps per resolution
7. `chart.remove()` in `onCleanup` + ResizeObserver
8. Resolution enum validation on API
9. Distinguish "symbol unknown" 404 vs "no candles yet" empty-200

### Deferred (v2)
- Redis cache on `/candles` keyed by `(symbol, resolution, from, to)`
- Keyboard shortcuts (`D/5/1/H`, `S` split, `C/A` chart type)
- Draggable split divider
- Log price scale toggle

---

## Assessment

**Ready to implement once B1–B3 are resolved.** The architecture is clean, the scope is disciplined, and the component boundaries are correct. The issues flagged here are concrete and inexpensive to fix at spec time — much cheaper than discovering them mid-implementation.

**Risk level:** Low-Medium (retention boundary and index gap are the real risks; UI gaps are easy to resolve).

**Estimated effort (post-fixes):** backend 4–5h (+ 1h migration/tests), frontend 6–8h, integration + manual QA 2h.
