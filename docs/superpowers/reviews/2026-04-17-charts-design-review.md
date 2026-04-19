# Charts Module Design Review

**Date:** 2026-04-17
**Reviewer:** Claude (Opus 4.7)
**Spec:** `2026-04-17-charts-design.md`

---

## Summary

Well-structured, practical design with clear scope boundaries. The lightweight-charts choice is sound for the use case. A few areas need clarification before implementation.

---

## Strengths

1. **Clear scope definition** — v1 explicitly excludes complexity creep (no indicators, no 3/4 panel grids, no persistence yet)
2. **Practical rendering choice** — lightweight-charts is industry-standard, lightweight, and canvas-based
3. **Smart split behavior** — defaulting panel 2 to next logical timeframe is good UX
4. **Non-blocking error states** — each panel fails independently; 5xx has retry button
5. **No N+1 concerns addressed** — single query per request, filtered by stock_id and time range

---

## Questions & Clarifications

### 1. API Auth (Critical)
> "Auth: no ownership check — candle data is not user-specific"

**Question:** Is there any rate limiting or abuse prevention? A user could hammer `/api/stocks/{symbol}/candles` with various symbols/resolutions. Consider:
- Per-IP or per-user rate limits
- Caching layer for popular symbols (Redis?)

### 2. Timezone Handling Edge Cases
> "chart-utils.ts handles the offset so pre-market UTC hours don't cut to the wrong session date"

**Question:** What about halfl-day trading days (Black Friday, day after Thanksgiving)? The "today" lookback for 5m/15m may return unexpected volume/behavior.

### 3. Stats Bar — Open Price
> "Open: **Intraday:** first bar `open` of the session"

**Clarification needed:** What if the first intraday bar is 9:35 AM (9:30 had no trades)? Should this display the "official" open from `daily_candles` instead, with a visual indicator?

### 4. 52W High/Low Source
> "52W High/Low: `week_52_high` / `week_52_low` from `realtime_quotes`"

**Question:** What happens when `realtime_quotes` is stale or hasn't been updated for that symbol today? Fallback behavior?

### 5. Empty Intraday Data
> "No intraday data — market may be closed. Switch to D."

**Question:** What about pre-market (before 9:30 ET) and after-hours? Should we show "Pre-market data not available — market opens at 9:30 ET"?

---

## Missing Items

### 1. Data Freshness Indicator
User can't tell if chart data is current. Suggest adding:
- Timestamp of last candle (e.g., "Last updated: 4:00 PM ET")
- Visual indicator for stale data (>15 min old for intraday)

### 2. Keyboard Shortcuts
Not mentioned but valuable for power users:
- `D` / `5m` / `15m` / `1H` — switch timeframes
- `S` — toggle split
- `C` / `A` — toggle chart type

### 3. Mobile Fallback
Spec says "Mobile layout deferred" but what happens on mobile? Currently:
- Two-pane split likely unusable on narrow screens
- Should right pane collapse into a modal/sheet on tap?

### 4. Loading Skeleton Design
Spec says "show a skeleton placeholder" but no visual spec. Define:
- Number of skeleton bars?
- Pulse animation or static gray?

---

## Technical Considerations

### 1. API Response Size
No limit specified on date range. Consider:
- Max `from`-to` span (e.g., 5 years for daily)
- Pagination if returning >10K candles?

### 2. Database Indexes
Ensure these exist before querying:
```sql
-- Suggested indexes
CREATE INDEX idx_intraday_candles_stock_res_time ON intraday_candles(stock_id, resolution, timestamp);
CREATE INDEX idx_daily_candles_stock_time ON daily_candles(stock_id, timestamp);
```

### 3. lightweight-charts License
It's Mozilla Public License 2.0. Confirm this is acceptable for your project's commercial use case.

### 4. Canvas Memory Leaks
Multiple chart instances (split view) + timeframe switching = potential canvas element leaks. Ensure:
- `chart.timeScale().destroy()` called on unmount
- No dangling event listeners

---

## Consistency Check vs Existing Architecture

| Concern | Status |
|---------|--------|
| Data flows through existing `DataProvider`? | ⚠️ New endpoint — not using DataProvider abstraction |
| Uses existing SQLAlchemy models? | ✅ `intraday_candles`, `daily_candles` |
| Follows error handling patterns? | ✅ Per-panel, non-blocking |
| Follows testing strategy? | ❌ No test section — add test plan |

---

## Recommended Actions

### Before Implementation
1. [ ] Clarify API rate limiting strategy
2. [ ] Define halfl-day trading behavior
3. [ ] Add test plan section to spec (unit + integration)
4. [ ] Confirm MPL 2.0 license acceptability
5. [ ] Add database migration for suggested indexes

### During Implementation
1. [ ] Add data freshness timestamp to stats bar
2. [ ] Implement canvas cleanup on unmount
3. [ ] Add mobile collapse behavior (even if basic)
4. [ ] Document timezone edge cases in `chart-utils.ts`

### v2 Considerations
1. [ ] Redis caching for popular symbol/timeframe combos
2. [ ] Keyboard shortcut handlers
3. [ ] Persist split/chart-type state to localStorage

---

## Assessment

**Ready for implementation** with minor clarifications. The design is pragmatic, scoped well, and avoids overengineering. Address the rate limiting and test plan items before coding begins.

**Risk Level:** Low

**Estimated Effort:** 8-12 hours (backend: 4h, frontend: 6h, tests: 2h)
