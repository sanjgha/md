# EMA Pullback + RS Scanner — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `ema_pullback_rs` daily scanner — long-only, 9/21 EMA pullback with healthy RSI and Mansfield RS vs. SPY — and wire it into the unified scanner registry so it runs alongside `pullback_continuation` in the 4:15 PM ET EOD job.

**Architecture:** New scanner class at `src/scanner/scanners/ema_pullback_rs.py`, new pure-function relative-strength helper at `src/scanner/indicators/relative_strength.py`, one new field (`benchmark_candles`) on `ScanContext`, and an executor change to fetch SPY's daily candles once per run and pass them into every per-stock context. Reference spec: `docs/superpowers/specs/2026-05-13-ema-pullback-rs-scanner-design.md`.

**Tech Stack:** Python 3.11+, numpy, SQLAlchemy 2.x, pytest, testcontainers (Docker required for integration tests), ruff (lint+format), mypy.

---

## File Structure

**Create:**
- `src/scanner/indicators/relative_strength.py` — pure function `compute_mansfield_rs(stock_candles, benchmark_candles, sma_period, slope_lookback) -> dict | None`. Handles timestamp alignment, Dorsey ratio, 260-bar SMA, Mansfield value, slope check.
- `src/scanner/scanners/ema_pullback_rs.py` — `EmaPullbackRsScanner(Scanner)`. Implements the 5-gate pipeline. Never raises.
- `tests/unit/test_relative_strength.py` — unit tests for the helper.
- `tests/unit/test_ema_pullback_rs_scanner.py` — unit tests for the scanner (mirrors `test_pullback_continuation_scanner.py`).
- `tests/integration/test_ema_pullback_rs_integration.py` — testcontainers Postgres integration tests for executor → scanner → DB persistence.

**Modify:**
- `src/scanner/context.py` — add `benchmark_candles: List[Candle] = field(default_factory=list)`.
- `src/scanner/executor.py` — add `_load_benchmark_candles(symbol="SPY")`; call once at top of `run_eod`; pass into every `ScanContext`.
- `src/scanner/registry_factory.py` — add `"ema_pullback_rs"` to `REGISTERED_SCANNER_NAMES`; register inside `build_scanner_registry()`.
- `tests/unit/scanner/test_registry_factory.py` — extend existing tests to include `ema_pullback_rs`.

**Reference (do not modify):**
- `src/scanner/scanners/pullback_continuation.py` — same shape, same never-raise contract, same metadata-rounding convention.
- `src/scanner/indicators/moving_averages.py` — `EMA` indicator (already registered).
- `src/scanner/indicators/momentum.py` — `RSI` indicator (already registered).

---

## Task 1: Relative-strength helper module (TDD)

**Files:**
- Create: `tests/unit/test_relative_strength.py`
- Create: `src/scanner/indicators/relative_strength.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_relative_strength.py`:

```python
"""Unit tests for Mansfield Relative Strength helper."""

from datetime import datetime, timedelta
import numpy as np
import pytest

from src.data_provider.base import Candle
from src.scanner.indicators.relative_strength import compute_mansfield_rs


def _make_candles(closes: list[float], start: datetime | None = None) -> list[Candle]:
    """Build a list of Candles with sequential daily timestamps; OHLV are stubs."""
    start = start or datetime(2025, 1, 1)
    return [
        Candle(
            timestamp=start + timedelta(days=i),
            open=c, high=c, low=c, close=c, volume=1_000_000,
        )
        for i, c in enumerate(closes)
    ]


def test_mansfield_positive_when_stock_outperforms():
    # Stock rises 30%, benchmark rises 10% over 300 bars; ratio is rising.
    n = 300
    stock = _make_candles(list(np.linspace(100, 130, n)))
    bench = _make_candles(list(np.linspace(100, 110, n)))
    result = compute_mansfield_rs(stock, bench, sma_period=260, slope_lookback=21)
    assert result is not None
    assert result["mansfield"] > 0
    assert result["rs_slope_ok"] is True


def test_mansfield_zero_when_perfectly_correlated():
    n = 300
    closes = list(np.linspace(100, 150, n))
    stock = _make_candles(closes)
    bench = _make_candles(closes)
    result = compute_mansfield_rs(stock, bench, sma_period=260, slope_lookback=21)
    assert result is not None
    # RS line is constant (100); Mansfield should be ~0 (within float tolerance).
    assert abs(result["mansfield"]) < 1e-6
    assert result["rs_slope_ok"] is False  # constant line is not rising


def test_mansfield_negative_when_underperforming():
    n = 300
    stock = _make_candles(list(np.linspace(100, 105, n)))   # +5%
    bench = _make_candles(list(np.linspace(100, 140, n)))   # +40%
    result = compute_mansfield_rs(stock, bench, sma_period=260, slope_lookback=21)
    assert result is not None
    assert result["mansfield"] < 0
    assert result["rs_slope_ok"] is False


def test_slope_ok_true_when_rs_rising_recently():
    # Stock flat for long stretch, then sprints in the final ~30 bars — slope rising.
    n = 300
    stock_closes = [100.0] * (n - 30) + list(np.linspace(100, 130, 30))
    bench_closes = [100.0] * n
    stock = _make_candles(stock_closes)
    bench = _make_candles(bench_closes)
    result = compute_mansfield_rs(stock, bench, sma_period=260, slope_lookback=21)
    assert result is not None
    assert result["rs_slope_ok"] is True


def test_slope_ok_false_when_rs_flat_recently():
    # Stock outperformed earlier, flat in the last 30 bars.
    n = 300
    stock_closes = list(np.linspace(100, 130, n - 30)) + [130.0] * 30
    bench_closes = [100.0] * n
    stock = _make_candles(stock_closes)
    bench = _make_candles(bench_closes)
    result = compute_mansfield_rs(stock, bench, sma_period=260, slope_lookback=21)
    assert result is not None
    assert result["rs_slope_ok"] is False


def test_returns_none_when_insufficient_aligned_bars():
    stock = _make_candles([100.0] * 100)
    bench = _make_candles([100.0] * 100)
    result = compute_mansfield_rs(stock, bench, sma_period=260, slope_lookback=21)
    assert result is None


def test_aligns_by_timestamp_inner_join():
    # Stock has dates Jan 1-300; benchmark skips Jan 5 and Jan 6 → aligned should be 298.
    stock = _make_candles(list(np.linspace(100, 130, 300)))
    bench_full = _make_candles(list(np.linspace(100, 110, 300)))
    bench = [c for c in bench_full if c.timestamp.day not in (5, 6) or c.timestamp.month != 1]
    result = compute_mansfield_rs(stock, bench, sma_period=260, slope_lookback=21)
    assert result is not None
    # rs_line length equals number of aligned bars (298).
    assert len(result["rs_line"]) == 298


def test_returns_none_on_nan_input():
    stock_closes = [100.0] * 300
    stock_closes[-1] = float("nan")
    stock = _make_candles(stock_closes)
    bench = _make_candles([100.0] * 300)
    result = compute_mansfield_rs(stock, bench, sma_period=260, slope_lookback=21)
    assert result is None


def test_returns_expected_keys():
    n = 300
    stock = _make_candles(list(np.linspace(100, 130, n)))
    bench = _make_candles(list(np.linspace(100, 110, n)))
    result = compute_mansfield_rs(stock, bench, sma_period=260, slope_lookback=21)
    assert set(result.keys()) == {
        "rs_line", "rs_sma", "rs_today", "rs_sma_today",
        "mansfield", "rs_slope_ok",
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_relative_strength.py -v`
Expected: All tests fail with `ModuleNotFoundError: No module named 'src.scanner.indicators.relative_strength'`.

- [ ] **Step 3: Implement the helper**

Create `src/scanner/indicators/relative_strength.py`:

```python
"""Mansfield Relative Strength helper — pure function, not registered in IndicatorCache.

The cache keys on a single candle series; a two-series indicator (stock vs. benchmark)
doesn't fit that model cleanly. Callers pass benchmark candles in directly.
"""

from typing import List, Optional

import numpy as np

from src.data_provider.base import Candle


def compute_mansfield_rs(
    stock_candles: List[Candle],
    benchmark_candles: List[Candle],
    sma_period: int = 260,
    slope_lookback: int = 21,
) -> Optional[dict]:
    """Align stock + benchmark by timestamp, compute Dorsey ratio, Mansfield, slope.

    Returns dict with keys (rs_line, rs_sma, rs_today, rs_sma_today, mansfield,
    rs_slope_ok), or None if fewer than `sma_period` aligned bars or if any
    relevant tail value is NaN/inf.
    """
    if not stock_candles or not benchmark_candles:
        return None

    stock_by_ts = {c.timestamp: c.close for c in stock_candles}
    bench_by_ts = {c.timestamp: c.close for c in benchmark_candles}
    aligned_ts = sorted(set(stock_by_ts.keys()) & set(bench_by_ts.keys()))

    if len(aligned_ts) < sma_period:
        return None

    stock_arr = np.array([stock_by_ts[t] for t in aligned_ts], dtype=float)
    bench_arr = np.array([bench_by_ts[t] for t in aligned_ts], dtype=float)

    if not (np.all(np.isfinite(stock_arr)) and np.all(np.isfinite(bench_arr))):
        return None
    if np.any(bench_arr == 0):
        return None

    rs_line = (stock_arr / bench_arr) * 100.0

    weights = np.ones(sma_period) / sma_period
    rs_sma = np.convolve(rs_line, weights, mode="valid")

    if not np.all(np.isfinite(rs_sma[-1:])) or not np.all(np.isfinite(rs_line[-(slope_lookback + 1):])):
        return None
    if rs_sma[-1] == 0:
        return None

    rs_today = float(rs_line[-1])
    rs_sma_today = float(rs_sma[-1])
    mansfield = (rs_today / rs_sma_today - 1.0) * 100.0
    rs_slope_ok = bool(rs_line[-1] > rs_line[-1 - slope_lookback])

    return {
        "rs_line": rs_line,
        "rs_sma": rs_sma,
        "rs_today": rs_today,
        "rs_sma_today": rs_sma_today,
        "mansfield": float(mansfield),
        "rs_slope_ok": rs_slope_ok,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_relative_strength.py -v`
Expected: All 9 tests PASS.

- [ ] **Step 5: Lint & format**

Run: `ruff format src/scanner/indicators/relative_strength.py tests/unit/test_relative_strength.py && ruff check src/scanner/indicators/relative_strength.py tests/unit/test_relative_strength.py`
Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add src/scanner/indicators/relative_strength.py tests/unit/test_relative_strength.py
git commit -m "feat: Mansfield relative-strength helper for stock-vs-benchmark scanning"
```

---

## Task 2: Add `benchmark_candles` field to `ScanContext`

**Files:**
- Modify: `src/scanner/context.py`
- Create: append to `tests/unit/test_scanner_implementations.py` (existing file with scanner-related tests) — OR a small new file. We'll append.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_scanner_implementations.py`:

```python
def test_scan_context_defaults_benchmark_candles_to_empty_list():
    """Existing scanners that don't pass benchmark_candles should still construct cleanly."""
    from src.scanner.context import ScanContext
    from src.scanner.indicators.cache import IndicatorCache

    ctx = ScanContext(
        stock_id=1,
        symbol="AAPL",
        daily_candles=[],
        intraday_candles={},
        indicator_cache=IndicatorCache({}),
    )
    assert ctx.benchmark_candles == []


def test_scan_context_accepts_benchmark_candles():
    from datetime import datetime
    from src.data_provider.base import Candle
    from src.scanner.context import ScanContext
    from src.scanner.indicators.cache import IndicatorCache

    spy_candles = [
        Candle(timestamp=datetime(2025, 1, 1), open=100, high=100, low=100, close=100, volume=1)
    ]
    ctx = ScanContext(
        stock_id=1,
        symbol="AAPL",
        daily_candles=[],
        intraday_candles={},
        indicator_cache=IndicatorCache({}),
        benchmark_candles=spy_candles,
    )
    assert len(ctx.benchmark_candles) == 1
    assert ctx.benchmark_candles[0].close == 100
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_scanner_implementations.py::test_scan_context_defaults_benchmark_candles_to_empty_list tests/unit/test_scanner_implementations.py::test_scan_context_accepts_benchmark_candles -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'benchmark_candles'`.

- [ ] **Step 3: Add the field**

Edit `src/scanner/context.py`. Final file:

```python
"""Scan context module for passing data to scanner instances."""

from dataclasses import dataclass, field
from typing import Dict, List
import numpy as np
from src.data_provider.base import Candle
from src.scanner.indicators.cache import IndicatorCache


@dataclass
class ScanContext:
    """Context passed to scanners during execution."""

    stock_id: int
    symbol: str
    daily_candles: List[Candle]
    intraday_candles: Dict[str, List[Candle]]
    indicator_cache: IndicatorCache
    benchmark_candles: List[Candle] = field(default_factory=list)

    def get_indicator(self, name: str, **kwargs) -> np.ndarray:
        """Retrieve (or calculate once) an indicator from the cache."""
        return self.indicator_cache.get_or_compute(name, self.daily_candles, **kwargs)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_scanner_implementations.py -v -k "benchmark_candles"`
Expected: Both new tests PASS. Also run the full file to confirm nothing broke: `pytest tests/unit/test_scanner_implementations.py -v` → all pass.

- [ ] **Step 5: Commit**

```bash
git add src/scanner/context.py tests/unit/test_scanner_implementations.py
git commit -m "feat: add benchmark_candles field to ScanContext (default empty list)"
```

---

## Task 3: Scanner skeleton — class, constants, returns empty list

**Files:**
- Create: `src/scanner/scanners/ema_pullback_rs.py`
- Create: `tests/unit/test_ema_pullback_rs_scanner.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_ema_pullback_rs_scanner.py`:

```python
"""Unit tests for ema_pullback_rs scanner."""

from datetime import datetime, timedelta
from typing import List
import numpy as np
import pytest

from src.data_provider.base import Candle
from src.scanner.context import ScanContext
from src.scanner.indicators.cache import IndicatorCache
from src.scanner.indicators.moving_averages import EMA
from src.scanner.indicators.momentum import RSI
from src.scanner.indicators.volatility import ATR
from src.scanner.scanners.ema_pullback_rs import EmaPullbackRsScanner


# ---------- Test helpers ----------

INDICATORS = {"ema": EMA(), "rsi": RSI(), "atr": ATR()}


def _ctx(daily: List[Candle], bench: List[Candle], stock_id: int = 1, symbol: str = "AAPL") -> ScanContext:
    return ScanContext(
        stock_id=stock_id,
        symbol=symbol,
        daily_candles=daily,
        intraday_candles={},
        indicator_cache=IndicatorCache(INDICATORS),
        benchmark_candles=bench,
    )


def _candles(closes: List[float], start: datetime | None = None, volume: int = 5_000_000) -> List[Candle]:
    start = start or datetime(2024, 1, 1)
    return [
        Candle(
            timestamp=start + timedelta(days=i),
            open=c * 0.999,
            high=c * 1.005,
            low=c * 0.995,
            close=c,
            volume=volume,
        )
        for i, c in enumerate(closes)
    ]


# ---------- Skeleton tests ----------


def test_scanner_class_attributes():
    scanner = EmaPullbackRsScanner()
    assert scanner.timeframe == "daily"
    assert "9/21" in scanner.description
    assert scanner.MIN_CANDLES == 280
    assert scanner.PRICE_MIN == 20.0
    assert scanner.BENCHMARK_SYMBOL == "SPY"
    assert scanner.RS_SMA_PERIOD == 260
    assert scanner.RS_SLOPE_LOOKBACK == 21
    assert scanner.PULLBACK_WINDOW == 5
    assert scanner.RSI_MIN == 40.0
    assert scanner.RSI_MAX == 70.0


def test_returns_empty_when_below_min_candles():
    daily = _candles([100.0] * 50)
    bench = _candles([100.0] * 50)
    assert EmaPullbackRsScanner().scan(_ctx(daily, bench)) == []


def test_returns_empty_when_benchmark_candles_missing():
    daily = _candles([100.0] * 300)
    assert EmaPullbackRsScanner().scan(_ctx(daily, bench=[])) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_ema_pullback_rs_scanner.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.scanner.scanners.ema_pullback_rs'`.

- [ ] **Step 3: Create the skeleton scanner**

Create `src/scanner/scanners/ema_pullback_rs.py`:

```python
"""9/21 EMA pullback scanner with Mansfield relative strength vs. benchmark."""

import logging
from typing import List

from src.scanner.base import Scanner, ScanResult
from src.scanner.context import ScanContext

logger = logging.getLogger(__name__)


class EmaPullbackRsScanner(Scanner):
    """Long-only daily scanner: trend stack + 9/21 EMA pullback + RSI band + Mansfield RS."""

    timeframe = "daily"
    description = "9/21 EMA pullback with healthy RSI and rising relative strength vs. SPY"

    # Universe / liquidity gates
    MIN_CANDLES = 280
    PRICE_MIN = 20.0
    AVG_DOLLAR_VOL_MIN = 50_000_000.0
    ATR_PCT_MIN = 1.5

    # Relative strength
    BENCHMARK_SYMBOL = "SPY"
    RS_SMA_PERIOD = 260
    RS_SLOPE_LOOKBACK = 21

    # Pullback geometry
    PULLBACK_WINDOW = 5
    EMA21_BUFFER_ATR = 0.25

    # RSI gate
    RSI_PERIOD = 14
    RSI_MIN = 40.0
    RSI_MAX = 70.0

    def scan(self, context: ScanContext) -> List[ScanResult]:
        """Return at most one ScanResult per stock; never raises."""
        try:
            candles = context.daily_candles
            if len(candles) < self.MIN_CANDLES:
                return []
            if not context.benchmark_candles:
                return []
            return []
        except Exception:
            logger.exception(f"EmaPullbackRsScanner failed for {context.symbol}")
            return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_ema_pullback_rs_scanner.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/scanner/scanners/ema_pullback_rs.py tests/unit/test_ema_pullback_rs_scanner.py
git commit -m "feat: ema_pullback_rs scanner skeleton with class constants"
```

---

## Task 4: Implement Gates 1 (liquidity) and 2 (trend stack)

**Files:**
- Modify: `src/scanner/scanners/ema_pullback_rs.py`
- Modify: `tests/unit/test_ema_pullback_rs_scanner.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/test_ema_pullback_rs_scanner.py`:

```python
def test_rejects_when_price_below_min():
    # 300 bars but final close is $10 — below PRICE_MIN of $20.
    daily = _candles([100.0] * 295 + [15.0, 12.0, 11.0, 10.5, 10.0])
    bench = _candles([100.0] * 300)
    assert EmaPullbackRsScanner().scan(_ctx(daily, bench)) == []


def test_rejects_when_dollar_volume_below_min():
    # Price OK but volume tiny → dollar volume below threshold.
    daily = _candles([100.0] * 300, volume=10_000)
    bench = _candles([100.0] * 300)
    assert EmaPullbackRsScanner().scan(_ctx(daily, bench)) == []


def test_rejects_when_atr_pct_below_min():
    # Flat candles → ATR ~0 → ATR% well below 1.5.
    daily = _candles([100.0] * 300, volume=5_000_000)
    bench = _candles([100.0] * 300)
    assert EmaPullbackRsScanner().scan(_ctx(daily, bench)) == []


def test_rejects_when_ema_stack_not_aligned():
    # Downtrend → EMA_9 < EMA_21 < EMA_50, the wrong order for our long-only filter.
    closes = list(np.linspace(150, 100, 300))
    daily = _candles(closes)
    bench = _candles([100.0] * 300)
    assert EmaPullbackRsScanner().scan(_ctx(daily, bench)) == []


def test_rejects_when_ema_50_not_rising():
    # Flat closes → EMA_50 slope = 0; flat is not > 0.
    daily = _candles([100.0] * 300, volume=5_000_000)
    bench = _candles([100.0] * 300)
    assert EmaPullbackRsScanner().scan(_ctx(daily, bench)) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_ema_pullback_rs_scanner.py -v -k "rejects_when_price or rejects_when_dollar or rejects_when_atr_pct or rejects_when_ema_stack or rejects_when_ema_50"`

Expected: All 5 currently PASS (the skeleton returns `[]` always). This is correct — we need to make sure they continue to pass after we add gates. But to make the test contract explicit, also add the happy-path canary at the bottom; **the canary should still fail** until later tasks.

Append to the test file:

```python
def _uptrend_with_pullback() -> tuple[List[Candle], List[Candle]]:
    """Build daily + benchmark candles that pass all 5 gates.

    Stock: 280 bars trending up from $50 → ~$150 with a 3-bar pullback ending 2 bars ago.
    Benchmark: 280 bars trending up from $100 → ~$110 (so stock outperforms).
    """
    n = 280
    rng = np.random.default_rng(seed=42)
    # Smooth uptrend with mild noise; final 5 bars: 2-bar pullback, 3 bars ago touches EMA_9.
    closes = list(np.linspace(50, 150, n - 5) + rng.normal(0, 0.5, n - 5))
    # Manually craft the last 5 bars to engineer a touch + reclaim.
    closes += [
        closes[-1] * 0.99,    # bar n-5
        closes[-1] * 0.96,    # bar n-4: deep pullback, will touch EMA_9
        closes[-1] * 0.96,    # bar n-3
        closes[-1] * 0.98,    # bar n-2
        closes[-1] * 1.02,    # bar n-1 (today): reclaim above EMA_9
    ]
    daily = _candles(closes)
    bench = _candles(list(np.linspace(100, 110, n)))
    return daily, bench


def test_emits_result_when_all_gates_pass():
    daily, bench = _uptrend_with_pullback()
    results = EmaPullbackRsScanner().scan(_ctx(daily, bench))
    assert len(results) == 1
    assert results[0].scanner_name == "ema_pullback_rs"
```

Run: `pytest tests/unit/test_ema_pullback_rs_scanner.py::test_emits_result_when_all_gates_pass -v`
Expected: FAIL — currently returns `[]`. This is the canary that proves we haven't finished.

- [ ] **Step 3: Implement Gates 1 and 2**

Edit `src/scanner/scanners/ema_pullback_rs.py`. Replace the `scan` method and add private helpers:

```python
import numpy as np

# ... (keep existing imports)

class EmaPullbackRsScanner(Scanner):
    # ... (keep existing class-level constants) ...

    def _liquidity_ok(self, candles, atr_arr) -> tuple[bool, float, float, float]:
        """Returns (ok, close, atr_val, atr_pct). atr_val=0 / atr_pct=0 on failure."""
        close = float(candles[-1].close)
        if close < self.PRICE_MIN:
            return (False, close, 0.0, 0.0)
        avg_dollar_vol = float(np.mean([c.close * c.volume for c in candles[-21:-1]]))
        if avg_dollar_vol < self.AVG_DOLLAR_VOL_MIN:
            return (False, close, 0.0, 0.0)
        if len(atr_arr) < 1:
            return (False, close, 0.0, 0.0)
        atr_val = float(atr_arr[-1])
        if not np.isfinite(atr_val) or atr_val <= 0:
            return (False, close, 0.0, 0.0)
        atr_pct = atr_val / close * 100.0
        if atr_pct < self.ATR_PCT_MIN:
            return (False, close, atr_val, atr_pct)
        return (True, close, atr_val, atr_pct)

    def _trend_ok(self, ema_9_arr, ema_21_arr, ema_50_arr) -> tuple[bool, float]:
        """Returns (ok, ema_50_slope_10). Slope is fractional change over last 10 bars."""
        if len(ema_9_arr) < 1 or len(ema_21_arr) < 1 or len(ema_50_arr) < 11:
            return (False, 0.0)
        if not (np.all(np.isfinite(ema_9_arr[-1:])) and np.all(np.isfinite(ema_21_arr[-1:]))
                and np.all(np.isfinite(ema_50_arr[-11:]))):
            return (False, 0.0)
        e9, e21, e50 = float(ema_9_arr[-1]), float(ema_21_arr[-1]), float(ema_50_arr[-1])
        if not (e9 > e21 > e50):
            return (False, 0.0)
        e50_back = float(ema_50_arr[-11])
        if e50_back == 0:
            return (False, 0.0)
        slope = (e50 - e50_back) / e50_back
        if slope <= 0:
            return (False, slope)
        return (True, slope)

    def scan(self, context: ScanContext) -> List[ScanResult]:
        """Return at most one ScanResult per stock; never raises."""
        try:
            candles = context.daily_candles
            if len(candles) < self.MIN_CANDLES:
                return []
            if not context.benchmark_candles:
                return []

            atr_arr = context.get_indicator("atr", period=14)
            ok, close, atr_val, atr_pct = self._liquidity_ok(candles, atr_arr)
            if not ok:
                return []

            ema_9_arr = context.get_indicator("ema", period=9)
            ema_21_arr = context.get_indicator("ema", period=21)
            ema_50_arr = context.get_indicator("ema", period=50)
            trend_ok, ema_50_slope_10 = self._trend_ok(ema_9_arr, ema_21_arr, ema_50_arr)
            if not trend_ok:
                return []

            # Remaining gates implemented in subsequent tasks.
            return []
        except Exception:
            logger.exception(f"EmaPullbackRsScanner failed for {context.symbol}")
            return []
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_ema_pullback_rs_scanner.py -v`
Expected: All rejection tests + skeleton tests PASS. `test_emits_result_when_all_gates_pass` still FAILS (canary still red — expected, more gates to add).

- [ ] **Step 5: Lint & format**

Run: `ruff format src/scanner/scanners/ema_pullback_rs.py tests/unit/test_ema_pullback_rs_scanner.py && ruff check src/scanner/scanners/ema_pullback_rs.py tests/unit/test_ema_pullback_rs_scanner.py`
Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add src/scanner/scanners/ema_pullback_rs.py tests/unit/test_ema_pullback_rs_scanner.py
git commit -m "feat: ema_pullback_rs Gate 1 (liquidity) + Gate 2 (trend stack)"
```

---

## Task 5: Implement Gate 3 (Mansfield RS + slope)

**Files:**
- Modify: `src/scanner/scanners/ema_pullback_rs.py`
- Modify: `tests/unit/test_ema_pullback_rs_scanner.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/test_ema_pullback_rs_scanner.py`:

```python
def test_rejects_when_mansfield_zero_or_negative():
    # Stock and benchmark identical → ratio constant → mansfield ~0, slope flat.
    closes = list(np.linspace(50, 150, 300))
    daily = _candles(closes)
    bench = _candles(closes)
    assert EmaPullbackRsScanner().scan(_ctx(daily, bench)) == []


def test_rejects_when_rs_slope_not_rising():
    # Stock outperforms cumulatively but flat-lined in the last ~30 bars → slope fails.
    n = 300
    stock_closes = list(np.linspace(50, 150, n - 30)) + [150.0] * 30
    bench_closes = list(np.linspace(100, 110, n))
    daily = _candles(stock_closes)
    bench = _candles(bench_closes)
    # This may or may not pass other gates; what matters is the RS slope reject.
    # We assert no result regardless.
    assert EmaPullbackRsScanner().scan(_ctx(daily, bench)) == []


def test_rejects_when_benchmark_alignment_too_short():
    daily = _candles([100.0] * 300)
    # Benchmark covers different date range with very small overlap.
    bench = _candles([100.0] * 100, start=datetime(2030, 1, 1))
    assert EmaPullbackRsScanner().scan(_ctx(daily, bench)) == []
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/unit/test_ema_pullback_rs_scanner.py -v -k "mansfield or rs_slope or benchmark_alignment"`
Expected: All PASS (because we currently return `[]` after gate 2 anyway). The canary `test_emits_result_when_all_gates_pass` is still red — that's the actual signal of progress.

- [ ] **Step 3: Implement Gate 3**

Edit `src/scanner/scanners/ema_pullback_rs.py`. Add import:

```python
from src.scanner.indicators.relative_strength import compute_mansfield_rs
```

Add private helper:

```python
    def _rs_ok(self, context: ScanContext) -> dict | None:
        """Returns the Mansfield dict on pass, else None."""
        rs = compute_mansfield_rs(
            context.daily_candles,
            context.benchmark_candles,
            sma_period=self.RS_SMA_PERIOD,
            slope_lookback=self.RS_SLOPE_LOOKBACK,
        )
        if rs is None:
            return None
        if rs["mansfield"] <= 0:
            return None
        if not rs["rs_slope_ok"]:
            return None
        return rs
```

Insert this call into `scan()` after the trend gate, before `return []`:

```python
            rs = self._rs_ok(context)
            if rs is None:
                return []

            # Remaining gates implemented in subsequent tasks.
            return []
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_ema_pullback_rs_scanner.py -v`
Expected: All existing tests still PASS. Canary still FAILS.

- [ ] **Step 5: Commit**

```bash
git add src/scanner/scanners/ema_pullback_rs.py tests/unit/test_ema_pullback_rs_scanner.py
git commit -m "feat: ema_pullback_rs Gate 3 (Mansfield RS + slope)"
```

---

## Task 6: Implement Gate 4 (pullback into 9/21 zone)

**Files:**
- Modify: `src/scanner/scanners/ema_pullback_rs.py`
- Modify: `tests/unit/test_ema_pullback_rs_scanner.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/test_ema_pullback_rs_scanner.py`:

```python
def test_rejects_when_no_pullback_touch_in_window():
    # Steady uptrend with no recent pullback into the 9/21 zone.
    n = 300
    closes = list(np.linspace(50, 150, n))
    daily = _candles(closes)
    bench = _candles(list(np.linspace(100, 110, n)))
    assert EmaPullbackRsScanner().scan(_ctx(daily, bench)) == []


def test_rejects_when_close_below_ema9_today():
    # Build an uptrend, then have today's close drop below EMA_9 — failed reclaim.
    n = 300
    closes = list(np.linspace(50, 150, n - 1)) + [80.0]  # collapse on the last bar
    daily = _candles(closes)
    bench = _candles(list(np.linspace(100, 110, n)))
    assert EmaPullbackRsScanner().scan(_ctx(daily, bench)) == []
```

The `test_rejects_when_today_is_the_touching_bar` and `test_rejects_when_pullback_blew_through_ema21` cases are checked implicitly by the happy-path canary (which engineers a touch 2-3 bars ago, not today, and holds within the buffer).

- [ ] **Step 2: Run tests**

Run: `pytest tests/unit/test_ema_pullback_rs_scanner.py -v -k "no_pullback_touch or close_below_ema9"`
Expected: Both PASS (still returning `[]` after gate 3). Canary still FAILS.

- [ ] **Step 3: Implement Gate 4**

Add private helper to `src/scanner/scanners/ema_pullback_rs.py`:

```python
    def _find_pullback_touch(
        self,
        candles,
        ema_9_arr,
        ema_21_arr,
        atr_arr,
    ) -> dict | None:
        """Look back over PULLBACK_WINDOW bars [today-1 .. today-PULLBACK_WINDOW] for a
        bar whose low touched EMA_9 but held above EMA_21 − EMA21_BUFFER_ATR × ATR.

        Returns dict {touch_offset, touch_low, touch_ema_9, touch_ema_21} or None.
        Today (offset -1) is excluded; we want the touch to be in the past.
        """
        n = len(candles)
        if len(ema_9_arr) < self.PULLBACK_WINDOW + 1 or len(ema_21_arr) < self.PULLBACK_WINDOW + 1:
            return None
        if len(atr_arr) < self.PULLBACK_WINDOW + 1:
            return None

        most_recent_touch: dict | None = None
        # Scan from oldest to newest so we end with the most recent qualifying touch.
        for k in range(self.PULLBACK_WINDOW, 1, -1):
            # offset -k means k bars ago; k ranges from PULLBACK_WINDOW down to 2.
            bar = candles[-k]
            e9 = float(ema_9_arr[-k])
            e21 = float(ema_21_arr[-k])
            atr = float(atr_arr[-k])
            if not (np.isfinite(e9) and np.isfinite(e21) and np.isfinite(atr) and atr > 0):
                continue
            if bar.low <= e9 and bar.low >= e21 - self.EMA21_BUFFER_ATR * atr:
                most_recent_touch = {
                    "touch_offset": -k,
                    "touch_low": float(bar.low),
                    "touch_ema_9": e9,
                    "touch_ema_21": e21,
                }
        return most_recent_touch
```

Insert into `scan()` after the RS gate:

```python
            touch = self._find_pullback_touch(candles, ema_9_arr, ema_21_arr, atr_arr)
            if touch is None:
                return []
            if close <= float(ema_9_arr[-1]):
                return []

            # Remaining gates implemented in subsequent tasks.
            return []
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_ema_pullback_rs_scanner.py -v`
Expected: All existing tests PASS. Canary still FAILS (RSI gate + metadata not yet wired).

- [ ] **Step 5: Commit**

```bash
git add src/scanner/scanners/ema_pullback_rs.py tests/unit/test_ema_pullback_rs_scanner.py
git commit -m "feat: ema_pullback_rs Gate 4 (pullback touch into 9/21 zone)"
```

---

## Task 7: Implement Gate 5 (RSI band), metadata builder, happy-path passes

**Files:**
- Modify: `src/scanner/scanners/ema_pullback_rs.py`
- Modify: `tests/unit/test_ema_pullback_rs_scanner.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/test_ema_pullback_rs_scanner.py`:

```python
def test_rejects_when_rsi_below_40():
    # Engineer the same setup as the happy path, but compress closes so RSI ends < 40.
    daily, bench = _uptrend_with_pullback()
    # Replace last 30 bars with a slow decline → RSI(14) drops below 40.
    n = len(daily)
    decline = list(np.linspace(daily[-31].close, daily[-31].close * 0.85, 30))
    new_candles = []
    for i, close in enumerate(decline):
        ts = daily[-30 + i].timestamp
        new_candles.append(Candle(
            timestamp=ts,
            open=close * 1.001, high=close * 1.005, low=close * 0.995,
            close=close, volume=5_000_000,
        ))
    daily = daily[:-30] + new_candles
    assert EmaPullbackRsScanner().scan(_ctx(daily, bench)) == []


def test_rejects_when_rsi_above_70():
    # Vertical run-up at the end → RSI > 70.
    daily, bench = _uptrend_with_pullback()
    n = len(daily)
    sprint = list(np.linspace(daily[-31].close, daily[-31].close * 1.40, 30))
    new_candles = []
    for i, close in enumerate(sprint):
        ts = daily[-30 + i].timestamp
        new_candles.append(Candle(
            timestamp=ts,
            open=close * 0.999, high=close * 1.005, low=close * 0.995,
            close=close, volume=5_000_000,
        ))
    daily = daily[:-30] + new_candles
    assert EmaPullbackRsScanner().scan(_ctx(daily, bench)) == []


def test_result_metadata_shape():
    daily, bench = _uptrend_with_pullback()
    results = EmaPullbackRsScanner().scan(_ctx(daily, bench))
    assert len(results) == 1
    md = results[0].metadata
    expected_keys = {
        "close", "atr_14", "atr_pct",
        "ema_9", "ema_21", "ema_50", "ema_50_slope_10",
        "rsi_14",
        "rs_today", "rs_sma_today", "mansfield_rs",
        "rs_line_21_bars_ago", "rs_slope_pct", "benchmark_symbol",
        "pullback_touch_idx_offset", "pullback_touch_low",
        "pullback_touch_ema_9", "pullback_touch_ema_21",
        "signal_date",
    }
    assert set(md.keys()) == expected_keys
    assert md["benchmark_symbol"] == "SPY"
    assert 40 <= md["rsi_14"] <= 70
    assert md["mansfield_rs"] > 0
    assert md["pullback_touch_idx_offset"] < 0  # in the past, not today
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/unit/test_ema_pullback_rs_scanner.py -v`
Expected: RSI rejection tests will PASS once we add the gate; the canary + metadata-shape test will fail until step 3 below.

- [ ] **Step 3: Implement Gate 5 + metadata builder**

In `src/scanner/scanners/ema_pullback_rs.py`, replace `scan()` and add `_build_result`:

```python
    def _build_result(
        self,
        context: ScanContext,
        candles,
        close: float,
        atr_val: float,
        atr_pct: float,
        ema_9_arr,
        ema_21_arr,
        ema_50_arr,
        ema_50_slope_10: float,
        rsi_today: float,
        rs: dict,
        touch: dict,
    ) -> ScanResult:
        rs_line = rs["rs_line"]
        rs_21_ago = float(rs_line[-1 - self.RS_SLOPE_LOOKBACK])
        rs_slope_pct = (rs["rs_today"] - rs_21_ago) / rs_21_ago * 100.0 if rs_21_ago != 0 else 0.0
        metadata = {
            "close": round(close, 4),
            "atr_14": round(atr_val, 4),
            "atr_pct": round(atr_pct, 4),
            "ema_9": round(float(ema_9_arr[-1]), 4),
            "ema_21": round(float(ema_21_arr[-1]), 4),
            "ema_50": round(float(ema_50_arr[-1]), 4),
            "ema_50_slope_10": round(ema_50_slope_10, 6),
            "rsi_14": round(rsi_today, 2),
            "rs_today": round(rs["rs_today"], 4),
            "rs_sma_today": round(rs["rs_sma_today"], 4),
            "mansfield_rs": round(rs["mansfield"], 4),
            "rs_line_21_bars_ago": round(rs_21_ago, 4),
            "rs_slope_pct": round(rs_slope_pct, 4),
            "benchmark_symbol": self.BENCHMARK_SYMBOL,
            "pullback_touch_idx_offset": int(touch["touch_offset"]),
            "pullback_touch_low": round(touch["touch_low"], 4),
            "pullback_touch_ema_9": round(touch["touch_ema_9"], 4),
            "pullback_touch_ema_21": round(touch["touch_ema_21"], 4),
            "signal_date": candles[-1].timestamp.strftime("%Y-%m-%d"),
        }
        return ScanResult(
            stock_id=context.stock_id,
            scanner_name="ema_pullback_rs",
            metadata=metadata,
        )

    def scan(self, context: ScanContext) -> List[ScanResult]:
        """Return at most one ScanResult per stock; never raises."""
        try:
            candles = context.daily_candles
            if len(candles) < self.MIN_CANDLES:
                return []
            if not context.benchmark_candles:
                return []

            atr_arr = context.get_indicator("atr", period=14)
            ok, close, atr_val, atr_pct = self._liquidity_ok(candles, atr_arr)
            if not ok:
                return []

            ema_9_arr = context.get_indicator("ema", period=9)
            ema_21_arr = context.get_indicator("ema", period=21)
            ema_50_arr = context.get_indicator("ema", period=50)
            trend_ok, ema_50_slope_10 = self._trend_ok(ema_9_arr, ema_21_arr, ema_50_arr)
            if not trend_ok:
                return []

            rs = self._rs_ok(context)
            if rs is None:
                return []

            touch = self._find_pullback_touch(candles, ema_9_arr, ema_21_arr, atr_arr)
            if touch is None:
                return []
            if close <= float(ema_9_arr[-1]):
                return []

            rsi_arr = context.get_indicator("rsi", period=self.RSI_PERIOD)
            if len(rsi_arr) < 1 or not np.isfinite(rsi_arr[-1]):
                return []
            rsi_today = float(rsi_arr[-1])
            if not (self.RSI_MIN <= rsi_today <= self.RSI_MAX):
                return []

            return [
                self._build_result(
                    context, candles, close, atr_val, atr_pct,
                    ema_9_arr, ema_21_arr, ema_50_arr, ema_50_slope_10,
                    rsi_today, rs, touch,
                )
            ]
        except Exception:
            logger.exception(f"EmaPullbackRsScanner failed for {context.symbol}")
            return []
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/test_ema_pullback_rs_scanner.py -v`
Expected: All tests PASS, including the canary `test_emits_result_when_all_gates_pass` and `test_result_metadata_shape`.

If `test_rejects_when_rsi_below_40` or `_above_70` doesn't pass: the synthetic candle generator may produce an unexpected RSI. Adjust the engineered sequence in those tests until RSI is genuinely outside the band. The point of these tests is to verify the gate rejects, so the test fixture is what needs tuning.

- [ ] **Step 5: Lint, format, type-check**

Run: `ruff format src/ tests/ && ruff check src/scanner/scanners/ema_pullback_rs.py tests/unit/test_ema_pullback_rs_scanner.py && mypy src/scanner/scanners/ema_pullback_rs.py --ignore-missing-imports`
Expected: No errors.

- [ ] **Step 6: Commit**

```bash
git add src/scanner/scanners/ema_pullback_rs.py tests/unit/test_ema_pullback_rs_scanner.py
git commit -m "feat: ema_pullback_rs Gate 5 (RSI) + metadata + happy path"
```

---

## Task 8: Edge cases & never-raise contract

**Files:**
- Modify: `tests/unit/test_ema_pullback_rs_scanner.py`

- [ ] **Step 1: Write the tests**

Add to `tests/unit/test_ema_pullback_rs_scanner.py`:

```python
def test_never_raises_on_pathological_input():
    # Empty candles
    assert EmaPullbackRsScanner().scan(_ctx([], [])) == []
    # NaN injected
    daily = _candles([100.0] * 300)
    # Force NaN in the last close.
    daily[-1] = Candle(
        timestamp=daily[-1].timestamp, open=100, high=100, low=100,
        close=float("nan"), volume=1_000_000,
    )
    bench = _candles([100.0] * 300)
    assert EmaPullbackRsScanner().scan(_ctx(daily, bench)) == []


def test_returns_empty_when_today_is_the_touching_bar():
    """Same-bar wick-and-reclaim: today touches EMA_9 AND closes above it. Reject."""
    daily, bench = _uptrend_with_pullback()
    # Replace the last 2 bars: take the bar 5 ago and put a touch on TODAY.
    n = len(daily)
    last = daily[-1]
    # Make today's low pierce EMA_9 (we use a low about 5% under today's close).
    daily[-1] = Candle(
        timestamp=last.timestamp,
        open=last.close * 0.98, high=last.close * 1.01, low=last.close * 0.93,
        close=last.close, volume=last.volume,
    )
    # Erase any earlier touch by raising lows on bars [-5..-2].
    for k in range(2, 6):
        b = daily[-k]
        daily[-k] = Candle(
            timestamp=b.timestamp, open=b.open, high=b.high,
            low=b.close * 0.99, close=b.close, volume=b.volume,
        )
    assert EmaPullbackRsScanner().scan(_ctx(daily, bench)) == []
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/unit/test_ema_pullback_rs_scanner.py -v`
Expected: All PASS (scanner already never-raises and the touching-bar gate is already in `_find_pullback_touch`, which only scans offsets `-PULLBACK_WINDOW..-2`).

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_ema_pullback_rs_scanner.py
git commit -m "test: ema_pullback_rs edge cases (pathological input, same-bar touch)"
```

---

## Task 9: Executor — load SPY once per run, pass into every context

**Files:**
- Modify: `src/scanner/executor.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_scanner_implementations.py`:

```python
def test_executor_loads_benchmark_candles_once_per_run(tmp_path, monkeypatch):
    """Verify ScannerExecutor.run_eod calls the benchmark-loader once, not per stock."""
    from src.scanner.executor import ScannerExecutor
    from src.scanner.registry import ScannerRegistry
    from src.output.base import OutputHandler

    class NullOutput(OutputHandler):
        def emit_scan_result(self, result): pass

    call_counter = {"count": 0}

    def fake_load_benchmark(self, symbol="SPY"):
        call_counter["count"] += 1
        return []

    monkeypatch.setattr(ScannerExecutor, "_load_benchmark_candles", fake_load_benchmark)

    executor = ScannerExecutor(
        registry=ScannerRegistry(),
        indicators_registry={},
        output_handler=NullOutput(),
        db=None,
    )
    # Three stocks; expect the helper to be called exactly once total.
    stocks = {1: ("AAA", []), 2: ("BBB", []), 3: ("CCC", [])}
    executor.run_eod(stocks)
    assert call_counter["count"] == 1


def test_executor_passes_benchmark_candles_into_context(monkeypatch):
    """Verify the benchmark candles loaded once are passed into every per-stock context."""
    from datetime import datetime
    from src.data_provider.base import Candle
    from src.scanner.base import Scanner, ScanResult
    from src.scanner.executor import ScannerExecutor
    from src.scanner.registry import ScannerRegistry
    from src.output.base import OutputHandler

    class CapturingScanner(Scanner):
        captured: list = []
        def scan(self, context):
            CapturingScanner.captured.append(len(context.benchmark_candles))
            return []

    class NullOutput(OutputHandler):
        def emit_scan_result(self, result): pass

    spy = [Candle(timestamp=datetime(2025, 1, i + 1), open=100, high=100, low=100, close=100, volume=1)
           for i in range(5)]
    monkeypatch.setattr(ScannerExecutor, "_load_benchmark_candles", lambda self, symbol="SPY": spy)

    registry = ScannerRegistry()
    registry.register("capturing", CapturingScanner())
    executor = ScannerExecutor(
        registry=registry, indicators_registry={}, output_handler=NullOutput(), db=None
    )
    executor.run_eod({1: ("AAA", []), 2: ("BBB", [])})
    assert CapturingScanner.captured == [5, 5]
```

Run: `pytest tests/unit/test_scanner_implementations.py -v -k "loads_benchmark or passes_benchmark"`
Expected: FAIL — `AttributeError: ... has no attribute '_load_benchmark_candles'`.

- [ ] **Step 2: Implement the executor change**

Edit `src/scanner/executor.py`. Final file:

```python
"""Scanner executor: runs all registered scanners for stocks with batch commits."""

import logging
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.data_provider.base import Candle
from src.db.models import DailyCandle, ScannerResult as ScannerResultModel, Stock
from src.output.base import OutputHandler
from src.scanner.base import ScanResult
from src.scanner.context import ScanContext
from src.scanner.indicators.cache import IndicatorCache
from src.scanner.registry import ScannerRegistry

logger = logging.getLogger(__name__)


class ScannerExecutor:
    """Executes scanners for stocks with batch commits and ORM-to-dataclass conversion."""

    BENCHMARK_FETCH_LIMIT = 320  # ≥ MIN_CANDLES (280) + buffer

    def __init__(
        self,
        registry: ScannerRegistry,
        indicators_registry: Dict,
        output_handler: OutputHandler,
        db: Optional[Session] = None,
    ):
        self.registry = registry
        self.indicators_registry = indicators_registry
        self.output_handler = output_handler
        self.db = db

    def _to_candles(self, orm_candles) -> List[Candle]:
        return [
            Candle(
                timestamp=c.timestamp,
                open=float(c.open),
                high=float(c.high),
                low=float(c.low),
                close=float(c.close),
                volume=int(c.volume),
            )
            for c in orm_candles
        ]

    def _load_benchmark_candles(self, symbol: str = "SPY") -> List[Candle]:
        """Fetch the last N daily candles for the benchmark symbol. Returns [] if absent."""
        if self.db is None:
            return []
        stock = self.db.execute(select(Stock).where(Stock.ticker == symbol)).scalar_one_or_none()
        if stock is None:
            logger.warning(f"Benchmark symbol {symbol} not found in stocks table — RS scanners will no-op.")
            return []
        rows = self.db.execute(
            select(DailyCandle)
            .where(DailyCandle.stock_id == stock.id)
            .order_by(DailyCandle.timestamp.desc())
            .limit(self.BENCHMARK_FETCH_LIMIT)
        ).scalars().all()
        # Reverse to chronological order.
        return self._to_candles(list(reversed(rows)))

    def run_eod(self, stocks_with_candles: Dict[int, tuple]) -> List[ScanResult]:
        """Run all scanners for each stock. Batch-commit all results per stock."""
        all_results: List[ScanResult] = []
        benchmark_candles = self._load_benchmark_candles()

        for stock_id, (symbol, daily_candles) in stocks_with_candles.items():
            indicator_cache = IndicatorCache(self.indicators_registry)
            context = ScanContext(
                stock_id=stock_id,
                symbol=symbol,
                daily_candles=daily_candles,
                intraday_candles={},
                indicator_cache=indicator_cache,
                benchmark_candles=benchmark_candles,
            )

            stock_results: List[ScanResult] = []
            for scanner_name, scanner in self.registry.list().items():
                try:
                    results = scanner.scan(context)
                    for result in results:
                        stock_results.append(result)
                        all_results.append(result)
                        self.output_handler.emit_scan_result(result)
                except Exception:
                    logger.exception(f"{scanner_name} failed for {symbol}")

            if stock_results:
                self._persist_results(stock_results, run_type="eod")

        return all_results

    def _persist_results(self, results: List[ScanResult], run_type: str = "eod") -> None:
        if not results or not self.db:
            return
        self.db.add_all(
            [
                ScannerResultModel(
                    stock_id=r.stock_id,
                    scanner_name=r.scanner_name,
                    result_metadata=r.metadata,
                    matched_at=r.matched_at,
                    run_type=run_type,
                )
                for r in results
            ]
        )
        self.db.commit()
```

Note: the column attribute may be `Stock.symbol` rather than `Stock.ticker`. **Before running tests, open `src/db/models.py` and verify which one the `Stock` model uses; substitute accordingly.**

- [ ] **Step 3: Run tests**

Run: `pytest tests/unit/test_scanner_implementations.py -v -k "loads_benchmark or passes_benchmark"`
Expected: Both PASS.

Run the broader test suite to confirm nothing else regressed: `pytest tests/unit/ -v`
Expected: All PASS.

- [ ] **Step 4: Commit**

```bash
git add src/scanner/executor.py tests/unit/test_scanner_implementations.py
git commit -m "feat: ScannerExecutor loads SPY benchmark candles once per EOD run"
```

---

## Task 10: Registry wiring + registry tests

**Files:**
- Modify: `src/scanner/registry_factory.py`
- Modify: `tests/unit/scanner/test_registry_factory.py`

- [ ] **Step 1: Write the failing tests**

Edit `tests/unit/scanner/test_registry_factory.py`. Update the existing `test_build_scanner_registry_returns_all_active_scanners`:

```python
def test_build_scanner_registry_returns_all_active_scanners():
    registry = build_scanner_registry()
    names = set(registry.list().keys())
    assert names == {
        "volume",
        "smart_money",
        "six_month_high",
        "weekly_options",
        "pullback_continuation",
        "ema_pullback_rs",
    }


def test_ema_pullback_rs_in_registered_names():
    assert "ema_pullback_rs" in REGISTERED_SCANNER_NAMES


def test_ema_pullback_rs_built_into_registry():
    scanner = build_scanner_registry().get("ema_pullback_rs")
    assert scanner is not None
    assert scanner.timeframe == "daily"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/scanner/test_registry_factory.py -v`
Expected: All three new/updated tests FAIL.

- [ ] **Step 3: Wire the scanner into the registry**

Edit `src/scanner/registry_factory.py`. Final file:

```python
"""Single source of truth for building the active scanner registry."""

from src.scanner.registry import ScannerRegistry

REGISTERED_SCANNER_NAMES: frozenset[str] = frozenset(
    {
        "volume",
        "smart_money",
        "SmartMoneyScanner",  # legacy name stored by class.__name__ before normalisation
        "six_month_high",
        "weekly_options",
        "pullback_continuation",
        "ema_pullback_rs",
    }
)


def build_scanner_registry() -> ScannerRegistry:
    """Instantiate and register all active scanners, returning a populated registry."""
    from src.scanner.scanners.volume_scan import VolumeScanner
    from src.scanner.scanners.smart_money import SmartMoneyScanner
    from src.scanner.scanners.six_month_high import SixMonthHighScanner
    from src.scanner.scanners.weekly_options import WeeklyOptionsScanner
    from src.scanner.scanners.pullback_continuation import PullbackContinuationScanner
    from src.scanner.scanners.ema_pullback_rs import EmaPullbackRsScanner

    registry = ScannerRegistry()
    registry.register("volume", VolumeScanner())
    registry.register("smart_money", SmartMoneyScanner())
    registry.register("six_month_high", SixMonthHighScanner())
    registry.register("weekly_options", WeeklyOptionsScanner())
    registry.register("pullback_continuation", PullbackContinuationScanner())
    registry.register("ema_pullback_rs", EmaPullbackRsScanner())
    return registry
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/scanner/test_registry_factory.py -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add src/scanner/registry_factory.py tests/unit/scanner/test_registry_factory.py
git commit -m "feat: register ema_pullback_rs in unified scanner registry"
```

---

## Task 11: Integration test — executor → scanner → DB persistence

**Files:**
- Create: `tests/integration/test_ema_pullback_rs_integration.py`

- [ ] **Step 1: Inspect existing integration test patterns**

Run: `pytest --collect-only tests/integration/test_scanner_result_run_type.py 2>&1 | head -20`

Open `tests/integration/test_scanner_result_run_type.py` and `tests/conftest.py` to find:
- `db_session` fixture name and behavior (truncates all tables after each test).
- Helpers for inserting `Stock` and `DailyCandle` rows.

You may discover the project has a `tests/fixtures/mock_data.py` helper — prefer it over hand-rolled inserts when available.

- [ ] **Step 2: Write the integration tests**

Create `tests/integration/test_ema_pullback_rs_integration.py`:

```python
"""Integration tests: ema_pullback_rs through ScannerExecutor with real Postgres."""

from datetime import datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest
from sqlalchemy import select

from src.db.models import DailyCandle, ScannerResult, Stock
from src.output.base import OutputHandler
from src.scanner.executor import ScannerExecutor
from src.scanner.indicators.moving_averages import EMA
from src.scanner.indicators.momentum import RSI
from src.scanner.indicators.volatility import ATR
from src.scanner.registry import ScannerRegistry
from src.scanner.scanners.ema_pullback_rs import EmaPullbackRsScanner


class NullOutput(OutputHandler):
    def emit_scan_result(self, result):
        pass


def _seed_stock_with_candles(db, ticker: str, closes: list[float], start: datetime) -> int:
    """Insert a Stock + matching DailyCandle rows. Returns stock_id."""
    # Use whatever column the Stock model exposes (ticker or symbol). Adjust if needed.
    stock = Stock(ticker=ticker)
    db.add(stock)
    db.flush()
    for i, close in enumerate(closes):
        db.add(DailyCandle(
            stock_id=stock.id,
            timestamp=start + timedelta(days=i),
            open=Decimal(f"{close * 0.999:.2f}"),
            high=Decimal(f"{close * 1.005:.2f}"),
            low=Decimal(f"{close * 0.995:.2f}"),
            close=Decimal(f"{close:.2f}"),
            volume=5_000_000,
        ))
    db.commit()
    return stock.id


def _happy_path_closes(n: int = 280) -> list[float]:
    rng = np.random.default_rng(seed=7)
    closes = list(np.linspace(50, 150, n - 5) + rng.normal(0, 0.5, n - 5))
    closes += [
        closes[-1] * 0.99, closes[-1] * 0.96, closes[-1] * 0.96,
        closes[-1] * 0.98, closes[-1] * 1.02,
    ]
    return closes


def test_eod_run_persists_ema_pullback_rs_result(db_session):
    start = datetime(2024, 1, 1)
    stock_closes = _happy_path_closes()
    spy_closes = list(np.linspace(100, 110, len(stock_closes)))
    stock_id = _seed_stock_with_candles(db_session, "AAA", stock_closes, start)
    _seed_stock_with_candles(db_session, "SPY", spy_closes, start)

    registry = ScannerRegistry()
    registry.register("ema_pullback_rs", EmaPullbackRsScanner())
    executor = ScannerExecutor(
        registry=registry,
        indicators_registry={"ema": EMA(), "rsi": RSI(), "atr": ATR()},
        output_handler=NullOutput(),
        db=db_session,
    )

    # Build daily_candles list for the stock (ORM → dataclass) matching what fetcher would pass.
    aaa = db_session.execute(select(DailyCandle).where(DailyCandle.stock_id == stock_id).order_by(DailyCandle.timestamp)).scalars().all()
    daily = executor._to_candles(aaa)
    executor.run_eod({stock_id: ("AAA", daily)})

    rows = db_session.execute(
        select(ScannerResult).where(ScannerResult.scanner_name == "ema_pullback_rs")
    ).scalars().all()
    assert len(rows) == 1
    md = rows[0].result_metadata
    assert md["benchmark_symbol"] == "SPY"
    assert 40 <= md["rsi_14"] <= 70
    assert md["mansfield_rs"] > 0


def test_eod_run_emits_nothing_when_benchmark_missing(db_session):
    """No SPY in stocks table → scanner returns [] for every stock, no error."""
    start = datetime(2024, 1, 1)
    stock_id = _seed_stock_with_candles(db_session, "AAA", _happy_path_closes(), start)

    registry = ScannerRegistry()
    registry.register("ema_pullback_rs", EmaPullbackRsScanner())
    executor = ScannerExecutor(
        registry=registry,
        indicators_registry={"ema": EMA(), "rsi": RSI(), "atr": ATR()},
        output_handler=NullOutput(),
        db=db_session,
    )

    aaa = db_session.execute(
        select(DailyCandle).where(DailyCandle.stock_id == stock_id).order_by(DailyCandle.timestamp)
    ).scalars().all()
    daily = executor._to_candles(aaa)
    executor.run_eod({stock_id: ("AAA", daily)})

    rows = db_session.execute(
        select(ScannerResult).where(ScannerResult.scanner_name == "ema_pullback_rs")
    ).scalars().all()
    assert rows == []
```

- [ ] **Step 3: Run integration tests**

Verify Docker is running: `docker ps` should not error.

Run: `pytest tests/integration/test_ema_pullback_rs_integration.py -v`
Expected: Both tests PASS.

If `Stock(ticker=...)` raises because the column is named `symbol`, fix the helper to use the actual column name. (Same applies to any other model attribute mismatch — inspect `src/db/models.py` first.)

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_ema_pullback_rs_integration.py
git commit -m "test: ema_pullback_rs integration tests with testcontainers"
```

---

## Task 12: Final verification

- [ ] **Step 1: Run the full local CI pipeline**

Run: `make ci`
Expected: All steps pass (ruff lint, ruff format check, mypy, full pytest suite with coverage).

If `make ci` fails:
- For lint/format errors → re-run `ruff format src/ tests/` and `ruff check src/ tests/` until clean.
- For mypy errors in the new files → fix type annotations (the helpers should already be typed; `compute_mansfield_rs` return is `Optional[dict]`).
- For test failures → debug per the relevant task. Do NOT mark complete with red tests.

- [ ] **Step 2: Run a sanity check on coverage**

Run: `pytest tests/unit/test_ema_pullback_rs_scanner.py tests/unit/test_relative_strength.py --cov=src/scanner/scanners/ema_pullback_rs --cov=src/scanner/indicators/relative_strength --cov-report=term-missing`
Expected: ≥90% line coverage on both new modules. Any genuinely-untested branches should either get a test or a documented reason.

- [ ] **Step 3: Verify scanner shows up in registry from a fresh import**

Run: `python -c "from src.scanner.registry_factory import build_scanner_registry; print(sorted(build_scanner_registry().list().keys()))"`
Expected: Output includes `'ema_pullback_rs'` alongside the existing 5 scanners.

- [ ] **Step 4: Commit any cleanup**

If `make ci` produced any auto-fixed formatting changes:

```bash
git add -u
git commit -m "chore: ruff format pass after ema_pullback_rs implementation"
```

(Skip if nothing changed.)

---

## Definition of Done

- All 12 tasks committed.
- `make ci` green.
- `build_scanner_registry().get("ema_pullback_rs")` returns an instance.
- `tests/unit/test_relative_strength.py` and `tests/unit/test_ema_pullback_rs_scanner.py` both at ≥90% line coverage on their target modules.
- `tests/integration/test_ema_pullback_rs_integration.py` passes against testcontainers Postgres.
- SPY is in the production `stocks` table and has ≥280 daily candles before the first real EOD run. (Operational prerequisite, not a code change — verify by `psql` or by checking the seed-universe output.)
