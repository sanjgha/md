# EMA Pullback + Relative Strength Scanner — Design

**Date:** 2026-05-13
**Status:** Spec — pending implementation
**Scanner name:** `ema_pullback_rs`
**Timeframe:** daily
**Direction:** long-only

## 1. Purpose

Detect stocks in confirmed uptrends pulling back into the 9/21 EMA zone, with healthy RSI momentum and durable + improving relative strength versus the index. The output is a setup signal only — no stop, target, or risk/reward metadata. Position management is the trader's responsibility.

This scanner is **independent** of the existing `pullback_continuation` scanner. It serves a different temperament: simpler, more mechanical, more frequent signals. `pullback_continuation` will continue to serve the high-conviction confluence use case.

## 2. Background — why these specific inputs

### 2.1 9/21 EMA trend stack

The 9-period and 21-period EMAs together define short-to-medium-term trend on the daily chart. The 50 EMA anchors medium-term direction. Stack alignment (`EMA_9 > EMA_21 > EMA_50`) plus a rising 50 EMA is the standard trend-follower filter: it rules out chop, downtrends, and freshly broken trends.

### 2.2 Pullback into the 9/21 zone

Pullbacks toward the 9/21 zone within an uptrend are statistically a favorable entry — the trend has not broken, but the recent extension has cooled. The "zone touch + reclaim" trigger (low pierces the band, today closes back above EMA_9) filters out one-way slides through the band that signal an actual trend change.

### 2.3 RSI(14) band 40–70

RSI in the 40–70 range during the trigger bar indicates momentum has cooled from the prior leg's high but has not turned bearish. Below 40 usually means the trend is changing character; above 70 means we are entering late into an already extended move.

### 2.4 Relative Strength versus index (Mansfield + slope)

Relative Strength here is not RSI. It is the stock's performance versus a benchmark — the canonical signal trend followers use (Weinstein, O'Neil, Minervini) to separate leaders from laggards. We use two complementary checks:

- **Mansfield RS > 0** — captures durable outperformance vs. the benchmark's own 1-year average. Single robust threshold.
- **RS line slope rising** — captures *improving* RS in the recent window. Filters out stocks that are positive on Mansfield only because of stale outperformance from months ago.

Both must hold. Together, they require both the long-term and recent-term relative-strength picture to be favorable. Web research (TrendSpider, ChartMill, Stage Analysis, Deepvue, Minervini interviews) confirms these are the two most-used RS checks in trend-following systems that do not require a cross-sectional rank.

### 2.5 Why not IBD percentile?

IBD-style RS rating (percentile rank across the universe) is the gold standard but requires a cross-sectional pre-pass over all 500 stocks before per-stock scanning can proceed. That is a larger infrastructure change. Mansfield + slope captures most of the same signal at per-stock cost. The cross-sectional rank can be added later as a confluence factor without disturbing this scanner's design.

## 3. Scope

### 3.1 In scope

- New scanner `ema_pullback_rs` registered in the unified scanner registry.
- New per-stock relative-strength helper module.
- New `benchmark_candles` field on `ScanContext`.
- Executor change to fetch benchmark candles once per run and pass them into every per-stock context.
- Unit, integration, and registry tests.

### 3.2 Out of scope

- Stop, target, risk/reward, or exit logic in scanner output.
- Short-direction symmetry. Long-only for v1.
- Sector-specific benchmarks (XLK, XLF, etc.). Single benchmark (SPY) for v1; module is structured so a per-stock sector benchmark can be added later.
- IBD-style percentile rank across the universe.
- Frontend / UI changes. The Scanner Control Panel picks up new scanners automatically via the existing registry-driven API endpoint.

## 4. Inputs and constants

```python
class EmaPullbackRsScanner(Scanner):
    timeframe = "daily"
    description = "9/21 EMA pullback with healthy RSI and rising relative strength vs. SPY"

    # Universe / liquidity gates (parallel to pullback_continuation)
    MIN_CANDLES = 280                       # buffer above the 260-bar Mansfield SMA so alignment gaps don't disqualify
    PRICE_MIN = 20.0
    AVG_DOLLAR_VOL_MIN = 50_000_000.0       # trailing 20 bars
    ATR_PCT_MIN = 1.5                       # filters dead names

    # Relative strength
    BENCHMARK_SYMBOL = "SPY"
    RS_SMA_PERIOD = 260                     # Mansfield's 52-week SMA expressed in trading days (52 × 5)
    RS_SLOPE_LOOKBACK = 21                  # ≈ one month

    # Pullback geometry
    PULLBACK_WINDOW = 5                     # look back 5 bars for the touching bar
    EMA21_BUFFER_ATR = 0.25                 # touch must hold within EMA_21 − 0.25×ATR

    # RSI gate
    RSI_PERIOD = 14
    RSI_MIN = 40.0
    RSI_MAX = 70.0
```

## 5. Signal pipeline

Gates are evaluated in order. First failure short-circuits. Order is chosen so cheapest gates run first.

### Gate 1 — Universe & liquidity

- `len(daily_candles) >= MIN_CANDLES`
- `close[-1] >= PRICE_MIN`
- `mean(close[-21:-1] * volume[-21:-1]) >= AVG_DOLLAR_VOL_MIN`
- `atr_14[-1] / close[-1] * 100 >= ATR_PCT_MIN`

### Gate 2 — Trend stack

- `EMA_9[-1] > EMA_21[-1] > EMA_50[-1]`
- `(EMA_50[-1] - EMA_50[-11]) / EMA_50[-11] > 0`

### Gate 3 — Relative strength (Mansfield + slope)

Compute via the helper described in §6.2.

- `mansfield > 0`, where `mansfield = (RS[-1] / RS_SMA252[-1] - 1) * 100`
- `RS[-1] > RS[-1 - RS_SLOPE_LOOKBACK]`

If `compute_mansfield_rs` returns `None` (insufficient aligned bars) → reject.

### Gate 4 — Pullback into the 9/21 zone

Find a touching bar `t` in the window `[n-PULLBACK_WINDOW .. n-2]` (today is index `n-1`; today must NOT be the touching bar):

- `candles[t].low <= EMA_9[t]` (touched the zone)
- `candles[t].low >= EMA_21[t] - EMA21_BUFFER_ATR * ATR_14[t]` (did not blow through)

If any bar in the window satisfies both, take the most recent such bar as the touch. Then require:

- `close[-1] > EMA_9[-1]` (reclaim today)

### Gate 5 — RSI gate

- `RSI_MIN <= RSI_14[-1] <= RSI_MAX`

If all 5 gates pass → emit a `ScanResult`.

## 6. Architecture

### 6.1 New field on `ScanContext`

```python
@dataclass
class ScanContext:
    stock_id: int
    symbol: str
    daily_candles: List[Candle]
    intraday_candles: Dict[str, List[Candle]]
    indicator_cache: IndicatorCache
    benchmark_candles: List[Candle] = field(default_factory=list)  # NEW
```

Default is an empty list so existing scanners that do not need it are unaffected.

### 6.2 New helper module — `src/scanner/indicators/relative_strength.py`

Pure function. Not registered in `IndicatorCache` because the cache keys on a single candle series; a two-series indicator does not fit that model cleanly.

```python
def compute_mansfield_rs(
    stock_candles: List[Candle],
    benchmark_candles: List[Candle],
    sma_period: int = 252,
    slope_lookback: int = 21,
) -> dict | None:
    """Align by timestamp (inner join), compute the RS line, its SMA, Mansfield value, and slope check.

    Returns:
        {
            "rs_line": np.ndarray,
            "rs_sma": np.ndarray,
            "rs_today": float,
            "rs_sma_today": float,
            "mansfield": float,
            "rs_slope_ok": bool,
        }
        or None if fewer than `sma_period` aligned bars (slope_lookback indexing is
        automatically satisfied since sma_period dominates).
    """
```

Implementation notes:

- Build a dict `{timestamp: close}` for each side, take `set.intersection` of timestamps, build aligned numpy arrays in sorted timestamp order.
- `rs_line = (stock_close / benchmark_close) * 100`.
- `rs_sma = SMA(rs_line, sma_period)`.
- `rs_today = rs_line[-1]`, `rs_sma_today = rs_sma[-1]`.
- `mansfield = (rs_today / rs_sma_today - 1) * 100`.
- `rs_slope_ok = rs_line[-1] > rs_line[-1 - slope_lookback]`.
- Return `None` if `len(aligned) < sma_period` or if any input contains NaN/inf in the relevant tail.

### 6.3 Executor change — `src/scanner/executor.py`

Add a single benchmark-load step at the top of `run_eod`:

```python
def run_eod(self, stocks_with_candles: Dict[int, tuple]) -> List[ScanResult]:
    benchmark_candles = self._load_benchmark_candles(symbol="SPY")
    # ... existing loop, but build context with benchmark_candles=benchmark_candles ...
```

`_load_benchmark_candles` reads from the same `daily_candles` table the stock candles come from, ordered by timestamp ascending, limited to the last `MIN_CANDLES + buffer` rows. If SPY has no rows, returns `[]` and logs a single warning — the scanner will then return `[]` for every stock without raising.

### 6.4 New scanner module — `src/scanner/scanners/ema_pullback_rs.py`

Mirrors the shape of `pullback_continuation.py`:

- Class-level constants (above).
- Small private helpers per gate: `_liquidity_ok`, `_trend_ok`, `_rs_ok`, `_find_pullback_touch`, `_rsi_ok`.
- A single `scan(context) -> List[ScanResult]` method.
- Wrap the whole `scan()` body in `try/except Exception`; on exception, `logger.exception(...)` and return `[]`. Never raises.

### 6.5 Registry wiring — `src/scanner/registry_factory.py`

Two edits, both required (the unified registry shipped in #51 makes this the single source of truth across every entry point):

1. Add `"ema_pullback_rs"` to the `REGISTERED_SCANNER_NAMES` frozenset.
2. Inside `build_scanner_registry()`, import the new class and call `registry.register("ema_pullback_rs", EmaPullbackRsScanner())`.

Automatic pickup downstream — no additional changes needed:

- EOD daily run (`ScannerExecutor.run_eod`, 4:15 PM ET) iterates `registry.list()` and runs every registered scanner.
- Pre-close run (3:45 PM ET) uses the same registry.
- Scanner Control Panel UI reads `description` and `timeframe` from the registry-backed API endpoint.

## 7. Output — `ScanResult` metadata shape

```python
metadata = {
    "close": float,
    "atr_14": float,
    "atr_pct": float,
    "ema_9": float,
    "ema_21": float,
    "ema_50": float,
    "ema_50_slope_10": float,                 # fractional change over last 10 bars
    "rsi_14": float,
    "rs_today": float,                        # Dorsey ratio value
    "rs_sma_today": float,                    # 252-bar SMA of the ratio
    "mansfield_rs": float,                    # ((rs/rs_sma) - 1) * 100
    "rs_line_21_bars_ago": float,             # to make the slope check auditable
    "rs_slope_pct": float,                    # (rs_today - rs_21_ago) / rs_21_ago * 100
    "benchmark_symbol": "SPY",
    "pullback_touch_idx_offset": int,         # negative offset of the touching bar (e.g. -3)
    "pullback_touch_low": float,
    "pullback_touch_ema_9": float,
    "pullback_touch_ema_21": float,
    "signal_date": "YYYY-MM-DD",
}
```

All floats rounded to 4 decimals (RSI to 2) — same convention as `pullback_continuation`.

## 8. Failure modes & non-raise contract

| Condition                                                | Behavior                                  |
|----------------------------------------------------------|-------------------------------------------|
| Stock has fewer than `MIN_CANDLES` daily candles         | Return `[]` silently                      |
| `context.benchmark_candles` is empty                     | Return `[]`; executor logs warning once   |
| Aligned bars after timestamp join < `RS_SMA_PERIOD`      | Return `[]`                               |
| Any indicator returns NaN/inf in the relevant tail       | Return `[]`                               |
| Any exception inside `scan()`                            | `logger.exception(...)`; return `[]`      |

Mirrors the contract used by every other scanner in this codebase.

## 9. Prerequisites

- **SPY must be in the universe.** SPY (or whatever `BENCHMARK_SYMBOL` is) must be present in the `stocks` table and have daily candles ingested by the existing fetcher. Verify before first run via `seed-universe` or manual insert. If absent, the scanner emits zero results (no crash) but is effectively a no-op.

## 10. Testing strategy

### 10.1 Unit — `tests/unit/scanner/scanners/test_ema_pullback_rs.py`

Synthetic numpy-generated `Candle` sequences. One test per gate, parameterized where it cuts duplication. Each rejection test perturbs only the variable under test so failures are diagnostic.

Happy path:
- `test_emits_result_when_all_gates_pass` — handcrafted uptrend + pullback into the 9/21 zone (touch 3 bars ago) + reclaim today + RSI ≈ 55 + SPY underperforming.

Rejection tests (one per gate condition):
- `test_rejects_when_below_min_candles`
- `test_rejects_when_price_below_min`
- `test_rejects_when_dollar_volume_below_min`
- `test_rejects_when_atr_pct_below_min`
- `test_rejects_when_ema_stack_not_aligned`
- `test_rejects_when_ema_50_not_rising`
- `test_rejects_when_mansfield_zero_or_negative`
- `test_rejects_when_rs_slope_not_rising`
- `test_rejects_when_no_pullback_touch_in_window`
- `test_rejects_when_today_is_the_touching_bar`
- `test_rejects_when_pullback_blew_through_ema21`
- `test_rejects_when_close_below_ema9_today`
- `test_rejects_when_rsi_below_40`
- `test_rejects_when_rsi_above_70`

Edge cases:
- `test_returns_empty_when_benchmark_candles_missing`
- `test_returns_empty_when_benchmark_alignment_too_short`
- `test_handles_nan_in_indicators_gracefully`
- `test_never_raises_on_pathological_input`

Metadata:
- `test_result_metadata_shape` — all keys present, types correct, rounding applied.

### 10.2 Unit — `tests/unit/scanner/indicators/test_relative_strength.py`

- `test_mansfield_positive_when_stock_outperforms`
- `test_mansfield_zero_when_perfectly_correlated`
- `test_mansfield_negative_when_underperforming`
- `test_slope_ok_true_when_rs_rising`
- `test_slope_ok_false_when_rs_flat`
- `test_returns_none_when_insufficient_aligned_bars`
- `test_aligns_by_timestamp_inner_join`

### 10.3 Integration — `tests/integration/scanner/test_ema_pullback_rs_integration.py`

Uses the `db_session` testcontainers fixture.

- `test_eod_run_persists_ema_pullback_rs_result` — seed SPY + one stock with handcrafted candles that pass all gates; run `ScannerExecutor.run_eod`; assert one row in `scanner_results` with `scanner_name == "ema_pullback_rs"` and well-formed JSONB metadata.
- `test_eod_run_loads_benchmark_candles_once` — spy/counter on `_load_benchmark_candles` confirms one call per run, not one per stock.
- `test_eod_run_handles_missing_spy_gracefully` — no SPY rows; run completes without error, emits no `ema_pullback_rs` results.

### 10.4 Registry — extend `tests/unit/scanner/test_registry_factory.py`

- `test_ema_pullback_rs_in_registered_names` — assert `"ema_pullback_rs" in REGISTERED_SCANNER_NAMES`.
- `test_ema_pullback_rs_built_into_registry` — `build_scanner_registry().get("ema_pullback_rs") is not None`.

Catches the common bug of editing one of the two registration points and forgetting the other.

### 10.5 Coverage

Aim for ≥90% line coverage on `ema_pullback_rs.py` and `relative_strength.py`. Project default `--cov=src` already reports this.

## 11. Open items / future extensions

These are explicitly deferred — not blockers for v1.

- **Sector benchmarks.** Replace SPY with the stock's sector ETF (XLK, XLF, XLV, etc.) for finer RS comparisons. Requires a stock→sector mapping table.
- **IBD-style RS percentile.** A cross-sectional pre-pass that produces a 1–99 rank per stock per run. Useful as a confluence factor (e.g. `rs_rating >= 70` in addition to Mansfield).
- **Short-side mirror.** Bidirectional version for downtrend pullbacks. Requires deciding what "underperforming SPY in a down market" means structurally.
- **Exit / position-management metadata.** If a future workflow wants this scanner to drive automated entries, we can add stop/target/RR fields without breaking the current contract.

## 12. References

- Stage Analysis — Mansfield Relative Performance Indicator: <https://www.stageanalysis.net/blog/4266/how-to-create-the-mansfield-relative-performance-indicator>
- TrendSpider — Dorsey & Mansfield Relative Strength: <https://trendspider.com/blog/new-indicators-added-dorsey-and-mansfield-relative-strength/>
- ChartMill — Mansfield Relative Strength: <https://www.chartmill.com/documentation/technical-analysis/indicators/35-Mansfield-Relative-Strength>
- Deepvue — Minervini stock screener / RS rating: <https://deepvue.com/screener/how-mark-minervini-screens-for-stocks/>
- Existing `pullback_continuation` scanner: `src/scanner/scanners/pullback_continuation.py`
- Unified scanner registry (#51): `src/scanner/registry_factory.py`
