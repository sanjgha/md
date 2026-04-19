# Watchlist Redesign — Design Review

**Reviewer:** Claude (Opus 4.6)
**Date:** 2026-04-16
**Spec:** `docs/superpowers/specs/2026-04-16-watchlist-redesign.md`

---

## Summary

The spec is well-scoped and the component decomposition is sound. It reuses existing add/remove endpoints correctly and the new `/quotes` endpoint is a reasonable extension. However, there are several unresolved interaction and data-freshness questions that will cause rework during implementation, plus one naming inconsistency with the existing DB model and one likely-N+1 backend risk. None of these are blockers — they're design decisions to make before you start coding, not after.

---

## Blockers (answer before writing code)

### 1. `chg` / `chg_pct` field naming contradicts the DB model
`RealtimeQuote` already has `change` and `change_pct` columns (`src/db/models.py:129-130`). The spec introduces new names (`chg`, `chg_pct`) in the JSON response.

Either:
- Match DB columns: use `change` / `change_pct` in the response schema.
- Or document why we're deliberately abbreviating at the API boundary.

Rest of the codebase uses snake_case and full words in Pydantic schemas (e.g. `symbol_count`, `is_auto_generated`). Abbreviating here is out of step.

### 2. EOD fallback needs a change calculation — spec is silent
For `source: "eod"`, what is `chg`? The `daily_candles` table only has OHLCV — no pre-computed delta. You need `close(today) - close(prev_trading_day)` across two rows. Spec just says "fall back to the latest row in `daily_candles`" — that gives you `last` but not `chg`/`chg_pct`.

Options to specify:
- Fetch the latest two `daily_candles` rows per stock and compute delta in-service.
- Or return `chg=null, chg_pct=null` when source is `eod` and let the frontend render "—".

The former is more useful but 2× the query load. Pick one and write it into the spec.

### 3. N+1 query risk in `get_quotes()`
The pseudocode ("for each symbol in the watchlist, check `realtime_quotes`... fall back to `daily_candles`") reads as per-symbol sequential lookups. For a 50-symbol watchlist this becomes 50–100 round-trips.

Spec should commit to a batch approach:
- One query for latest-per-`stock_id` in `realtime_quotes` (window function over `stock_id`).
- One query for latest-per-`stock_id` in `daily_candles` for the missing ones.
- Merge in Python.

Worth calling out because the naive implementation will pass tests and ship slow.

### 4. Ownership check on the new `/quotes` endpoint
Spec doesn't say that `GET /api/watchlists/{id}/quotes` must return 404 when the caller doesn't own the watchlist. Every other route in `routes.py` does this via `service.get_watchlist(watchlist_id, user_id)` — add the same guard here and say so in the spec.

---

## Unresolved interactions

### 5. Cache invalidation after add/remove
`category-group.tsx` owns quote data cached locally. Spec handles the initial load but not:

- **Add flow:** after `POST /symbols` succeeds, the new row renders with no quote. Do we (a) re-fetch all quotes, (b) fetch just that symbol's quote, or (c) render with "—" until the next reload? Option (b) requires a new endpoint. Option (a) is simple but wasteful. Pick one.
- **Remove flow:** fine — just drop the row.
- **Cross-session staleness:** a group expanded at 9:30 AM still shows the 9:30 prices at 3:00 PM. "Refresh on page reload" is the current answer but for an active trader this is painful. Consider a per-group refresh affordance (not streaming — just a manual click) as a small addition.

### 6. Only-one-group-expanded is a surprising constraint
TradingView's actual behavior is multi-expand with persistent scroll. Your spec has "only one group expanded at a time" — why? If the reason is screen real estate on narrow panes, say so. If it's state simplicity, it's the wrong trade-off: users will want SELL and BUY visible simultaneously.

Recommend: allow multi-expand, persist the expansion set in `localStorage`.

### 7. Selected-symbol edge cases
`dashboard.tsx` owns `selectedSymbol`. What happens when:

- The user deletes the currently-selected symbol? → Clear selection.
- The user collapses the group containing the selected symbol? → Keep selection (right pane still shows placeholder), or clear?
- The symbol is in a watchlist the user deletes? → Clear.

These are five lines of code but need to be explicit.

### 8. Loading and error states inside a group
Spec only describes the happy path. Missing:

- **Expansion → first paint:** show symbol list immediately (from `/symbols`), show skeleton placeholders for price cells until `/quotes` resolves.
- **`/quotes` fails:** render rows without prices, show an inline "Prices unavailable" banner, don't block interaction.
- **Add fails (network, not validation):** spec only covers "TSLA not found". Also handle 500s, timeouts, and the existing 400 "already exists" case.

### 9. Optimistic delete — restore position
Spec says "restore on error". Restoring at the end of the list is wrong; restore at the original index (or by `priority`). Worth one sentence.

### 10. Mobile / touch-only devices
Hover-to-reveal `✕` doesn't work on touch. Out of scope is fine, but the spec should say "desktop-only; mobile layout deferred" so we don't discover it in review.

---

## Smaller things

### 11. Scanner Results group in the mock is ambiguous
The ASCII mock shows `▶ Scanner Results` as a single bottom-level entry. In the current system, "Scanner Results" is a **category** that contains multiple auto-generated watchlists (e.g. "Price Action - Today", "Price Action - History", per `WatchlistGenerationService`). Either the mock is wrong or the redesign collapses them — clarify.

### 12. `source` dot indicator (● vs ○) is too subtle
Filled vs hollow circle at watchlist-row scale is hard to read. Consider a colored dot (e.g. green = realtime, grey = EOD) or a tooltip on hover. Minor, but this is the only signal of data freshness.

### 13. No refresh affordance at all
Even without streaming, a manual "↻" in each expanded group header is cheap and high-value for an EOD-transitioning-to-intraday workflow. Worth adding to v1.

### 14. Virtualization threshold
A "History" watchlist grows unbounded (`_create_or_append_watchlist`). At 500+ rows, un-virtualized rendering gets sluggish. Not a v1 requirement, but note it as "revisit if any watchlist exceeds ~200 symbols".

### 15. Keyboard navigation
↑/↓ to move through rows, Enter to select, `/` to focus the add input. TradingView-parity tasks, but worth a line even if deferred.

---

## Things the spec got right

- Clear out-of-scope list — right-pane content, streaming, create/rename UI.
- Reusing existing `POST`/`DELETE /symbols` endpoints; only the read path (`/quotes`) is new.
- Component split is correct — `category-group.tsx` is the right ownership boundary for quote state.
- No global store — matches the rest of the app (Solid signals, per-page).
- Deleting `watchlist-view.tsx` is the right call; leaving `edit-modal`/`create-modal` untouched is correct.
- `source` field on each quote is a good affordance for the "why is this price stale" question.

---

## Recommended changes to the spec before implementation

1. Resolve `chg` vs `change` naming.
2. Specify EOD `chg`/`chg_pct` computation (or explicitly null them).
3. Write one sentence committing to batch queries in `get_quotes()`.
4. Add ownership check requirement on the new endpoint.
5. Define post-add quote refresh behavior.
6. Justify or drop the single-expand constraint.
7. Enumerate selected-symbol edge cases (3 lines).
8. Add loading/error state descriptions for the group-expand flow.
9. Note that mobile layout is out of scope.
10. Clarify how Scanner Results watchlists render.

Everything else (refresh button, dot visibility, keyboard nav, virtualization) can be deferred with a note.
