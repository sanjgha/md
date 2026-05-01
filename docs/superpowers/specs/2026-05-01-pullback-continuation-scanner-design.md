# Pullback Continuation Scanner — Design

**Date:** 2026-05-01
**Branch (target):** `feat/pullback-continuation-scanner`
**Status:** Approved for implementation
**Author:** Sanjeev (with Claude)
**Supersedes:** `wave2_waveB_scanner_spec.md` (Elliott-labeled prior draft)

## Purpose

Surface daily, EOD-evaluated, mechanical entries on **high-quality pullbacks in confirmed trends** — bidirectional. Long signals fire on a pullback-continuation reclaim in a confirmed uptrend; short signals fire on a failed-bounce rejection after a confirmed trend break. Replaces the Elliott-labeled "Wave 2 / Wave B" framing of the prior spec with deterministic rules.

This scanner runs alongside existing EOD scanners (`price_action`, `momentum`, `volume`, `smart_money`, `six_month_high`, `weekly_options`) and emits at most one `ScanResult` per stock per day with `direction = "long" | "short"`.

## Edge: Pullback Continuation Confluence

Pullbacks in a strong trend are statistically the lowest-risk entry — the prior leg has confirmed direction, the pullback has shaken out weak holders, and re-entry on confirmation gets a tight stop just past the pullback extreme for the next swing leg. The five-rule confluence (trend + geometry + exhaustion + trigger + liquidity) raises base rate at the cost of fewer signals — same trade-off `WeeklyOptionsScanner` makes.

A single bidirectional scanner. The bullish (long) condition set is described first; the short set is the symmetric mirror.

### Required confluence (all five must hold)

**1. Trend confirmed (uptrend).**
- `EMA(9) > EMA(21) > EMA(50)` on the bar where the pullback began (the most recent swing high before today, call it bar `H`).
- `close[H] > EMA(21)[H]`.
- `EMA(50)[today] > EMA(50)[today−10]` (slope positive over the last 10 bars).

**2. Pullback geometry.**
- Bar `H` is a swing high in the last 3–15 bars (inclusive). "Swing high" = bar whose high exceeds the highs of the 2 bars before and 2 bars after — fractal-style, computed by the new `SwingPoints` indicator.
- Let `L` = swing low immediately preceding `H` (start of the up-leg). `up_leg = high[H] − low[L]`.
- Let `pullback_low` = lowest low between `H` and today.
- `retrace_pct = (high[H] − pullback_low) / up_leg` must be in `[0.38, 0.78]`.

**3. Exhaustion** — ≥2 of the following must have fired on **today, yesterday, or day-before**:
- **Support hold:** the bar's low touched a support level (a price tested ≥2× in the last 60 bars within ±0.5×ATR) and the bar closed above that level.
- **RSI(14) bullish divergence:** the bar made a lower low than the prior pullback low, but RSI(14) made a higher low than at the prior pullback low.
- **Volume surge:** the bar's volume > 1.2× the 20-day average volume.
- **MACD(12,26,9) histogram cross:** histogram crossed from negative to ≥0 on that bar.

**4. Trigger today.**
- `close[today] > EMA(9)[today]` AND `close[today] > max(high[today−1], high[today−2], high[today−3])`.

**5. Liquidity / universe** (applied before rule evaluation; identical to `WeeklyOptionsScanner`).
- `close ≥ $20`.
- 20-day avg dollar volume ≥ $50M.
- `ATR(14) / close ≥ 1.5%`.

If any of the five fails, no signal is emitted.

### Short side (mirror)

The short setup is "failed bounce after a trend break" — trend WAS up, broke recently, and today's bounce is rejecting at resistance. The mirror is structural, not literal: trend is checked at bar `H` (where the prior uptrend was last confirmed), trend break is checked at bar `L`.

- **Trend.** `EMA(9)[H] > EMA(21)[H] > EMA(50)[H]` AND `close[H] > EMA(21)[H]` — i.e., bar `H` (the prior swing high, start of the down-leg) was inside a confirmed uptrend. AND `close[L] < EMA(21)[L]` — bar `L` is below the 21-EMA, confirming the trend broke. AND `EMA(50)[today] ≤ EMA(50)[today−10]` (slope flat-to-negative).
- **Geometry.** `L` is a swing low in last 3–15 bars; `H` = swing high immediately preceding `L`. `down_leg = high[H] − low[L]`. `bounce_high` = highest high between `L` and today. `retrace_pct = (bounce_high − low[L]) / down_leg ∈ [0.38, 0.78]`.
- **Exhaustion** (≥2 of, today/yesterday/day-before): **resistance fail** (bar high touched resistance ±0.5×ATR and closed below it); **RSI(14) bearish divergence** (higher price high vs prior bounce high, lower RSI high); **volume surge** (>1.2× 20-day avg); **MACD histogram cross** from positive to ≤0.
- **Trigger today.** `close[today] < EMA(21)[today]` AND `close[today] < min(low[today−1], low[today−2], low[today−3])`.
- **Universe filter.** Same as long.

## Output

A single `ScanResult` per match. The scanner only evaluates today's bar — at most one signal per stock per day.

### Conviction scoring

Weighted sum, clamped to `[0, 100]`:

| Component | Weight | Best when |
|---|---|---|
| Exhaustion criteria count | 30 | 4 hits → 30; 3 → 22; 2 → 15 (minimum to qualify) |
| Retracement quality | 25 | Closer to 50–61.8% sweet-spot → max; 38% or 78% edges → 0 |
| Volume confirmation | 20 | Trigger-bar `volume / avg20` ratio: 1.0 → 0; 2.0+ → 20 |
| Trend slope strength | 15 | `\|EMA(9) − EMA(50)\| / EMA(50)` magnitude: 0% → 0; 5%+ → 15 |
| Distance to support (long) / resistance (short) | 10 | Tighter to nearest level (in ATR units) → max |

A score below 40 still emits a signal but flags it lower-conviction in metadata for downstream filtering.

### Metadata schema

```python
{
    "direction":           "long" | "short",
    "conviction_score":    int,          # 0-100
    "close":               float,
    "atr":                 float,
    "atr_pct":             float,        # atr / close * 100
    "ema_9":               float,
    "ema_21":              float,
    "ema_50":              float,
    "ema_50_slope_10":     float,        # (ema_50[today] − ema_50[today-10]) / ema_50[today-10]
    "rsi_14":              float,
    "macd_histogram":      float,
    "swing_anchor_idx":    int,          # bars-ago of bar H (long) / bar L (short)
    "swing_anchor_price":  float,        # high[H] (long) / low[L] (short)
    "leg_size":            float,        # up_leg (long) / down_leg (short)
    "pullback_extreme":    float,        # pullback_low (long) / bounce_high (short)
    "retrace_pct":         float,        # 0.38 - 0.78
    "exhaustion_count":    int,          # 2-4
    "exhaustion_reasons":  list[str],    # subset of {"support_hold","rsi_div","volume_surge","macd_cross"}
    "volume_ratio":        float,        # trigger-bar volume / 20-day avg
    "stop_level":          float,        # pullback_extreme − 0.5*ATR (long); + for short
    "target_level":        float,        # close + 1.618 * leg_size (long); − for short
    "risk_reward":         float,        # |target − close| / |close − stop|
    "signal_date":         "YYYY-MM-DD",
}
```

## Architecture

Mirrors the established scanner pattern.

```
src/scanner/
  scanners/
    pullback_continuation.py        # NEW — class PullbackContinuationScanner(Scanner)
    __init__.py                     # export PullbackContinuationScanner
  indicators/
    support_resistance.py           # ADD: SwingPoints indicator
    momentum.py                     # ADD: RSIDivergence helper (uses existing RSI)
                                    # (existing EMA, RSI, MACD, ATR reused)
src/main.py                         # register "pullback_continuation" in eod and schedule blocks
tests/unit/scanner/
  indicators/
    test_swing_points.py            # NEW
    test_rsi_divergence.py          # NEW
  scanners/
    test_pullback_continuation.py   # NEW
```

### New indicator: `SwingPoints`

Added to `src/scanner/indicators/support_resistance.py`. Fractal-style local-extreme detection over a configurable lookback (default 60). Bar `i` is a swing high if `high[i] > max(high[i−2..i−1])` AND `high[i] > max(high[i+1..i+2])`. Returns two aligned arrays of `(bar_index, price)` tuples for highs and lows. Reusable by future "wave 4 pullback", "head-and-shoulders", "double-top" scanners.

### New helper: `RSIDivergence`

Added to `src/scanner/indicators/momentum.py`. Pure function: takes a price series, an RSI series, and two pivot bar indices `(prior_pivot, current_pivot)`. Returns `(bullish_div: bool, bearish_div: bool)`. Bullish: `price[current] < price[prior]` AND `rsi[current] > rsi[prior]`. Bearish: mirror. No state.

### Scanner class

`PullbackContinuationScanner(Scanner)`:
- `timeframe = "daily"`
- `description = "Bidirectional pullback continuation: trend + geometry + exhaustion + trigger"`
- `MIN_CANDLES = 80` — needs 60-bar swing-point lookback + 20-day volume avg + buffer.
- Single public `scan(context: ScanContext) -> List[ScanResult]`.
- All indicators fetched via `context.get_indicator(...)` for cache reuse.
- Wraps the body in `try/except` with `logger.exception(...)`; never raises.

### Registration

In `src/main.py`, add `scanner_registry.register("pullback_continuation", PullbackContinuationScanner())` to **both** registration sites (the `eod` command block and the `schedule` command block). Output flows through the existing `CompositeOutputHandler`; results land in `scanner_results` with `scanner_name = "pullback_continuation"`.

### Schedule

No scheduler change. The existing `eod_scan` cron job at 4:15 PM ET picks the new scanner up via registration. The `pre_close_scan` job at 3:45 PM does **not** run this scanner — the trigger rule depends on the closing print.

## Data flow

```
EOD job → DataFetcher refreshes daily candles
        → ScannerExecutor iterates universe
            → For each stock:
                ScanContext built (candles + indicator cache)
                PullbackContinuationScanner.scan(context)
                    universe filter → indicators → 5-rule check → score → metadata
                ScanResult appended (if any)
            → CompositeOutputHandler persists to scanner_results + logs
```

## Error handling

- Scanner-level `try/except Exception` with `logger.exception` — never raises, never blocks other scanners. Same pattern as `SixMonthHighScanner` and `WeeklyOptionsScanner`.
- Insufficient candles (< `MIN_CANDLES = 80`) → return `[]` silently (debug-log only).
- No qualifying swing high in the 3–15 bar window → no signal.
- NaN / inf in any computed indicator field → skip emission.
- Universe filter failure → skip silently, no log noise.

## Testing

Unit tests using synthetic candle fixtures (no DB, no testcontainers).

| Test | What it verifies |
|---|---|
| `test_emits_long_on_clean_pullback` | Trend up, retrace 50%, ≥2 exhaustion, trigger today → exactly one long signal, metadata complete |
| `test_emits_short_on_failed_bounce` | Mirror setup → exactly one short signal |
| `test_no_signal_when_trend_missing` | EMAs unstacked → no signal |
| `test_no_signal_when_ema50_slope_negative` | Stack OK but EMA(50) flat-down → no signal |
| `test_no_signal_when_pullback_too_shallow` | retrace 25% → no signal |
| `test_no_signal_when_pullback_too_deep` | retrace 85% → no signal |
| `test_no_signal_when_pullback_too_recent` | swing-high 1 bar ago → no signal |
| `test_no_signal_when_pullback_stale` | swing-high 20 bars ago → no signal |
| `test_no_signal_when_only_one_exhaustion` | 1 of 4 exhaustion criteria → no signal |
| `test_exhaustion_window_spans_three_bars` | 1 criterion today + 1 criterion 2 bars ago → qualifies |
| `test_no_signal_when_trigger_below_3bar_high` | exhaustion OK, close > EMA(9) but ≤ 3-bar high → no signal |
| `test_universe_filter_price` | close < $20 → no signal |
| `test_universe_filter_dollar_volume` | avg $-vol < $50M → no signal |
| `test_universe_filter_atr` | ATR% < 1.5 → no signal |
| `test_insufficient_candles` | < 80 bars → no signal, no error |
| `test_conviction_score_bounds` | score always in `[0, 100]` |
| `test_metadata_complete` | all required fields present and typed correctly |
| `test_stop_target_math_long` | `stop = pullback_low − 0.5×ATR`, `target = close + 1.618 × up_leg` |
| `test_stop_target_math_short` | mirror |

Indicator unit tests:

| Test | What it verifies |
|---|---|
| `test_swing_points_basic` | Synthetic series with known peaks/troughs → indicator returns them |
| `test_swing_points_edges` | Peaks within 2 bars of array start/end excluded |
| `test_swing_points_constant` | Flat series → empty highs and lows |
| `test_rsi_divergence_bullish` | Lower price low + higher RSI low → `bullish_div = True` |
| `test_rsi_divergence_bearish` | Mirror |
| `test_rsi_divergence_none` | Both lows higher → both flags False |

No integration test required for v1 — the scanner uses only existing data paths.

## Out of scope (explicitly)

- Multi-day state machine / `WATCH → READY` persistence (chose stateless single-day evaluation in design).
- Backtesting framework (separate project).
- Multi-timeframe analysis (1h/15m confirmation) — daily only for v1.
- Watchlist auto-add on signal (manual workflow remains).
- Position sizing / order execution (scanner emits guidance only).
- Migrating `smart_money.py`'s private swing detection onto `SwingPoints` (deferred to a follow-up refactor PR to avoid Smart Money regressions).

## Decision log

- **Pattern reframe over Elliott labels** — mechanical, testable rules; avoids the subjective wave-counting problem of the prior spec.
- **Single bidirectional scanner** — mirrors `WeeklyOptionsScanner` ergonomics; direction is a metadata field.
- **Stateless single-day evaluation** — matches existing scanner architecture; no new tables, no state-transition logic.
- **Liquidity filter aligned with `WeeklyOptionsScanner`** — consistent universe across high-conviction directional scanners.
- **EMA-stack + EMA(50) slope for trend** — stack alone passes flat regimes; slope filters dying trends.
- **Bar-count + retracement % for geometry** — bar-count filters stale setups; retracement % filters shallow noise and over-deep failures. Together they bracket the "high-quality, recent, meaningful pullback" zone the Elliott Wave 2/Wave B labels were trying to capture.
- **Exhaustion within last 3 bars + trigger today** — captures the original spec's two-day notion (exhaustion bar ≠ entry bar) without going stateful.
- **ATR-based symmetric stops, 1.618× target** — scales buffer with volatility (0.5% on a $20 stock vs $400 stock differs); 1.618× extension matches Elliott projection convention.
- **Two new reusable indicators (`SwingPoints`, `RSIDivergence`)** — first-class indicators with caching, usable by future scanners (wave-4 pullback, double-top, head-and-shoulders).

## Implementation checklist (preview — full plan in writing-plans phase)

1. Add `SwingPoints` to `src/scanner/indicators/support_resistance.py` with unit tests.
2. Add `RSIDivergence` helper to `src/scanner/indicators/momentum.py` with unit tests.
3. Implement `PullbackContinuationScanner` in `src/scanner/scanners/pullback_continuation.py`.
4. Export in `src/scanner/scanners/__init__.py`.
5. Register in both blocks of `src/main.py`.
6. Add unit tests in `tests/unit/scanner/scanners/test_pullback_continuation.py`.
7. Run `make ci` clean.
8. Linear issue + Conventional Commit `feat: pullback-continuation EOD scanner (#NN)`.
