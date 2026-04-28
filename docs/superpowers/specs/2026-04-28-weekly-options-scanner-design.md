# Weekly Options Scanner — Design

**Date:** 2026-04-28
**Branch (target):** `feat/weekly-options-scanner`
**Status:** Approved for implementation
**Author:** Sanjeev (with Claude)

## Purpose

Surface daily, EOD-evaluated, high-conviction directional setups suitable for buying **weekly or next-weekly naked call/put options** on the underlying. Naked options have asymmetric risk against time decay; the scanner's edge must therefore favour stocks with compressed volatility (cheaper premium) that have just begun a confirmed directional move with volume.

This scanner runs alongside existing EOD scanners (`price_action`, `momentum`, `volume`, `smart_money`, `six_month_high`) and emits at most one signal per stock per day with `direction = "call" | "put"`.

## Edge: Squeeze-Break Confluence

A single bidirectional scanner. The bullish (call) condition set is described first; the put set is the symmetric mirror.

### Required confluence (all five must hold)

1. **Squeeze present.** Bollinger Band width = `(BB_upper − BB_lower) / BB_middle` over a 20-period window. Today's BB width must be in the **bottom 25th percentile** of the last 60 trading days. Compressed bands → option implied vol is comparatively low → premium is "on sale" relative to the stock's recent vol regime.
2. **Directional break.** Either:
   - Today's close > yesterday's BB upper band (bull) / < yesterday's BB lower band (bear), OR
   - Today's close > 20-day Donchian high (bull) / < 20-day Donchian low (bear).
3. **Trend alignment.** EMA(20) > EMA(50) and close > EMA(20) for a call. Reverse for a put. Filters counter-trend false breaks.
4. **Volume confirmation.** Today's volume ≥ **1.5×** the 20-day average volume.
5. **No overextension.** RSI(14) < 75 for calls, > 25 for puts. Avoids buying after a parabolic blow-off where mean reversion risk is elevated.

If any of the five fails, no signal is emitted.

### Universe / liquidity filters (applied before the rule set)

- `close ≥ $20` — sub-$20 names typically lack weekly options or have wide strike spacing.
- 20-day average dollar volume ≥ **$50M** — proxy for tight option spreads.
- `ATR(14) / close ≥ 1.5%` — minimum daily range to overcome theta on a weekly.

A stock failing any filter is skipped silently (no `ScanResult`).

## Output

A single `ScanResult` per match (most recent qualifying day if multiple bars qualify in lookback — but this scanner only evaluates *today*'s candle, so at most one).

### Metadata schema

```python
{
    "direction":          "call" | "put",
    "conviction_score":   int,    # 0-100, see scoring below
    "close":              float,
    "atr":                float,
    "atr_pct":            float,  # atr / close * 100
    "bb_width":           float,
    "bb_width_pctile":    float,  # 0-100, lower = tighter squeeze
    "volume_ratio":       float,  # today_volume / avg20_volume
    "ema_20":             float,
    "ema_50":             float,
    "rsi_14":             float,
    "break_type":         "bb_band" | "donchian" | "both",
    "suggested_expiry":   "weekly" | "next_weekly",
    "target_1_atr":       float,  # close ± 1 * ATR (strike-selection guide)
    "stop_level":         float,  # close ∓ 0.5 * ATR (invalidation)
    "signal_date":        "YYYY-MM-DD",
}
```

### Conviction scoring

Weighted sum, clamped to `[0, 100]`:

| Component | Weight | Best when |
|---|---|---|
| Squeeze tightness | 30 | `bb_width_pctile` low (0 → 30 pts, 25 → 0 pts) |
| Volume surge | 25 | `volume_ratio` high (1.5 → 0 pts, 3.0+ → 25 pts) |
| ATR % | 20 | Higher daily range → bigger expected weekly move |
| Trend slope | 15 | `(ema_20 − ema_50) / ema_50` magnitude |
| Break magnitude | 10 | How far close pierces breakout level, in ATR |

A score below 40 still emits a signal but flags it lower-conviction in the metadata for downstream filtering.

### Suggested expiry

- `weekly` if `atr_pct ≥ 2.5` — fast mover, theta is acceptable for a 5-day option.
- `next_weekly` (~10 trading days out) otherwise — buys time at the cost of more premium.

This is a **suggestion**, not an order. The scanner does not place trades.

## Architecture

Mirrors the established scanner pattern.

```
src/scanner/
  scanners/
    weekly_options.py            # NEW — class WeeklyOptionsScanner(Scanner)
  indicators/
    volatility.py                # ADD: BBWidthPercentile indicator
                                 # (existing BollingerBands and ATR reused)
    moving_averages.py           # reuse existing EMA
    momentum.py                  # reuse existing RSI
  scanners/__init__.py           # export WeeklyOptionsScanner
src/main.py                      # register "weekly_options" in both
                                 # registry blocks (eod and schedule paths)
tests/unit/scanner/scanners/
  test_weekly_options.py         # NEW
```

### New indicator: `BBWidthPercentile`

Added to `src/scanner/indicators/volatility.py`. Computes the rolling percentile rank of BB-width over a configurable lookback (default 60). Output is a 1-D numpy array aligned to candle indices where the indicator is defined; values are in `[0, 100]`. Reused only by this scanner today, but kept as a first-class indicator so other future "vol regime" scanners can pick it up.

### Scanner class

`WeeklyOptionsScanner(Scanner)`:
- `timeframe = "daily"`
- `description = "Bidirectional weekly-option setup: squeeze + directional break + trend + volume"`
- `MIN_CANDLES = 80` — needs 60-day percentile window plus 20-period BB plus a small buffer.
- Single public method `scan(context: ScanContext) -> List[ScanResult]`.
- Uses `context.get_indicator(...)` for all reused indicators so caching works.
- Wraps the entire body in `try/except` with `logger.exception(...)` per the established pattern.

### Registration

In `src/main.py` add `scanner_registry.register("weekly_options", WeeklyOptionsScanner())` to both registration sites (the `eod` command at line ~115 and the `schedule` command at line ~889). Output flows through the existing `CompositeOutputHandler`; results land in `scanner_results` with `scanner_name = "weekly_options"`.

### Schedule

No scheduler change. The existing `eod_scan` cron job at 4:15 PM ET picks the new scanner up by virtue of its registration. The `pre_close_scan` job at 3:45 PM does **not** run this scanner; the squeeze-break confluence is intentionally an EOD signal because volume confirmation needs the full session's tape.

## Data flow

```
EOD job → DataFetcher refreshes daily candles
        → ScannerExecutor iterates universe
            → For each stock:
                ScanContext built (candles + indicator cache)
                WeeklyOptionsScanner.scan(context)
                    universe filter → indicators → 5-rule check → score → metadata
                ScanResult appended (if any)
            → CompositeOutputHandler persists + logs
```

## Error handling

- Scanner-level `try/except Exception` with `logger.exception` — never raises, never blocks other scanners. Same pattern as `SixMonthHighScanner`.
- Insufficient candles → return `[]` silently (debug-log only).
- NaN / inf in any computed field → skip emission (treat as no signal).

## Testing

Unit tests using synthetic candle fixtures (no DB, no testcontainers needed):

| Test | What it verifies |
|---|---|
| `test_emits_call_on_clean_setup` | All five conditions met → exactly one call signal, metadata complete |
| `test_emits_put_on_mirror_setup` | Symmetric bear setup → put signal |
| `test_no_signal_when_no_squeeze` | BB width above 25th pctile → no signal |
| `test_no_signal_without_break` | Squeeze + trend but close inside bands → no signal |
| `test_trend_filter_blocks_counter_trend_break` | Bull break in downtrend → no signal |
| `test_volume_filter_blocks_quiet_break` | Volume < 1.5× → no signal |
| `test_overextended_call_blocked` | RSI ≥ 75 on bull → no signal |
| `test_overextended_put_blocked` | RSI ≤ 25 on bear → no signal |
| `test_universe_filter_price` | Close < $20 → no signal |
| `test_universe_filter_dollar_volume` | Avg $-vol < $50M → no signal |
| `test_universe_filter_atr` | ATR% < 1.5 → no signal |
| `test_insufficient_candles` | Fewer than 80 bars → no signal, no error |
| `test_conviction_score_bounds` | Score always in `[0, 100]` |
| `test_suggested_expiry_thresholds` | atr_pct = 2.4 → next_weekly; 2.6 → weekly |

One additional unit test for the new `BBWidthPercentile` indicator (sanity: rising BB-width series → percentile trends toward 100; constant series → 50 throughout).

No integration test required for v1 — the scanner uses only existing data paths.

## Out of scope (explicitly)

- Option chain ingestion, strike selection, or premium pricing.
- Position sizing or trade execution.
- Backtesting framework (handled separately if/when a backtester is built).
- IV-based filters (would need an option data feed; ATR% is the v1 proxy).
- Watchlist auto-add on signal (existing manual workflow remains).

## Decision log

- **Bidirectional single scanner** — chosen for ergonomics; direction is a metadata field, not a separate scanner. Easier to compare call vs put pipelines side by side.
- **Confluence over single-factor** — naked weeklies cannot tolerate weak signals; theta punishes slow movers. Five-rule confluence accepts fewer signals to raise base rate.
- **EOD only** — volume confirmation requires full-session tape; `pre_close_scan` would emit signals that flip after the close.
- **No IV filter in v1** — option data feed is not yet integrated; ATR% serves as a coarse vol proxy on the underlying.
- **`BBWidthPercentile` as a first-class indicator** — reusable for future vol-regime work, and aligns with the existing indicator/cache pattern.

## Implementation checklist (preview — full plan in writing-plans phase)

1. Add `BBWidthPercentile` to `src/scanner/indicators/volatility.py` with unit test.
2. Implement `WeeklyOptionsScanner` in `src/scanner/scanners/weekly_options.py`.
3. Export in `src/scanner/scanners/__init__.py`.
4. Register in both blocks of `src/main.py`.
5. Add unit tests in `tests/unit/scanner/scanners/test_weekly_options.py`.
6. Run `make ci` clean.
7. Linear issue + Conventional Commit `feat: weekly-options EOD scanner (#NN)`.
