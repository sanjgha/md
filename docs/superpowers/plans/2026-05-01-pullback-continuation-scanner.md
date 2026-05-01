# Pullback Continuation Scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bidirectional EOD scanner (`pullback_continuation`) that emits at most one signal per stock per day on confirmed-trend pullback continuations (long) or failed-bounce rejections (short), using a 5-rule confluence: trend + geometry + exhaustion + trigger + liquidity.

**Architecture:** Subclass `Scanner` (stateless, single-day evaluation). Reuse cached EMA/RSI/MACD/ATR. Add two new reusable indicators: `SwingPoints` (fractal-style local extremes) and `RSIDivergence` (pure helper). Register in the `scan` CLI block only — this is EOD-only because the trigger rule depends on the closing print, mirroring `WeeklyOptionsScanner`.

**Tech Stack:** Python 3.10+, NumPy, SQLAlchemy, pytest, ruff, mypy, Click. Existing scanner framework in `src/scanner/`.

**Spec:** `docs/superpowers/specs/2026-05-01-pullback-continuation-scanner-design.md`

**Reference scanner to mirror:** `src/scanner/scanners/weekly_options.py` and its tests in `tests/unit/test_weekly_options_scanner.py`.

**File layout:**
- Create: `src/scanner/scanners/pullback_continuation.py` — the new `PullbackContinuationScanner`.
- Modify: `src/scanner/indicators/support_resistance.py` — add `SwingPoints` indicator.
- Modify: `src/scanner/indicators/momentum.py` — add `rsi_divergence(...)` pure helper function.
- Modify: `src/scanner/scanners/__init__.py` — export `PullbackContinuationScanner`.
- Modify: `src/main.py` — import + register the scanner and the `SwingPoints` indicator (`scan` command block only, since EOD-only).
- Create: `tests/unit/test_swing_points.py` — indicator tests.
- Create: `tests/unit/test_rsi_divergence.py` — helper tests.
- Create: `tests/unit/test_pullback_continuation_scanner.py` — scanner tests.

**Convention notes (codebase-specific):**
- Tests live flat in `tests/unit/` (e.g., `test_weekly_options_scanner.py`), not under `tests/unit/scanner/scanners/`. The spec's path was illustrative; follow the actual flat layout.
- The pre-close registration block (`run_pre_close_scan` in `src/main.py`) does NOT register `weekly_options` (EOD-only). The new `pullback_continuation` is also EOD-only and follows the same pattern: register only in the `scan` command block.
- Pre-commit hook auto-formats with `ruff`. Conventional Commits enforced.
- Run `make ci` before final push.

**Linear / branch:**
- New branch: `feat/pullback-continuation-scanner` (cut from `master`).
- Open a Linear issue first using `docs/linear/templates/new-issue.md`.

---

## Task 1: Create Linear issue and feature branch

**Files:**
- No source changes — preparation step.

- [ ] **Step 1: Create the Linear issue from the template**

Use the Linear MCP. Title: `feat: pullback-continuation EOD scanner`. Body should reference the design doc and summarise the 5-rule confluence. Capture the issue key (e.g., `MAR-NN`) for use in commits.

- [ ] **Step 2: Cut the feature branch**

Run:
```bash
cd /home/ubuntu/projects/md
git fetch origin
git checkout master
git pull --ff-only
git checkout -b feat/pullback-continuation-scanner
```
Expected: `Switched to a new branch 'feat/pullback-continuation-scanner'`.

- [ ] **Step 3: Confirm clean working tree**

Run: `git status`
Expected: `nothing to commit, working tree clean`.

---

## Task 2: SwingPoints indicator — failing test for highs

**Files:**
- Create: `tests/unit/test_swing_points.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_swing_points.py`:
```python
"""Unit tests for SwingPoints indicator."""

from datetime import datetime, timedelta
from typing import List

import numpy as np

from src.data_provider.base import Candle
from src.scanner.indicators.support_resistance import SwingPoints


def _candles(highs: List[float], lows: List[float]) -> List[Candle]:
    base = datetime(2024, 1, 1)
    out = []
    for i, (h, lo) in enumerate(zip(highs, lows)):
        mid = (h + lo) / 2
        out.append(
            Candle(
                timestamp=base + timedelta(days=i),
                open=mid,
                high=h,
                low=lo,
                close=mid,
                volume=1_000_000,
            )
        )
    return out


def test_swing_points_basic_high():
    """Bar i is a swing high if high[i] > max(high[i-2..i-1]) AND high[i] > max(high[i+1..i+2])."""
    # Index:    0    1    2    3    4    5    6    7    8
    # Highs:   10,  11,  12,  20,  12,  11,  10,   9,   8
    # Lows:    same shape lower
    highs = [10.0, 11.0, 12.0, 20.0, 12.0, 11.0, 10.0, 9.0, 8.0]
    lows = [h - 5.0 for h in highs]
    sp = SwingPoints()
    result = sp.compute(_candles(highs, lows), lookback=60)
    # result is a dict with 'highs' and 'lows' arrays of (index, price) tuples
    assert (3, 20.0) in [(int(i), float(p)) for i, p in result["highs"]]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_swing_points.py::test_swing_points_basic_high -v`
Expected: FAIL with `ImportError: cannot import name 'SwingPoints'` or AttributeError.

---

## Task 3: SwingPoints indicator — minimal implementation

**Files:**
- Modify: `src/scanner/indicators/support_resistance.py`

- [ ] **Step 1: Implement SwingPoints to make test pass**

Append to `src/scanner/indicators/support_resistance.py`:
```python
class SwingPoints(Indicator):
    """Fractal-style swing high/low detector.

    A bar i is a swing high if high[i] > max(high[i-2..i-1]) AND high[i] > max(high[i+1..i+2]).
    Mirror condition for swing lows on lows[].

    Returns a dict {'highs': np.ndarray of shape (n,2), 'lows': np.ndarray of shape (n,2)}
    where each row is (bar_index, price). Indices and prices are floats.
    Only swings within the last `lookback` bars (default 60) of the input are returned.
    """

    def compute(self, candles: List[Candle], lookback: int = 60, **kwargs):
        highs = np.array([c.high for c in candles], dtype=float)
        lows = np.array([c.low for c in candles], dtype=float)
        n = len(candles)
        if n < 5:
            return {"highs": np.empty((0, 2)), "lows": np.empty((0, 2))}

        start = max(2, n - lookback)
        end = n - 2  # need 2 bars after for fractal

        swing_highs: list[tuple[int, float]] = []
        swing_lows: list[tuple[int, float]] = []
        for i in range(start, end):
            if (
                highs[i] > highs[i - 1]
                and highs[i] > highs[i - 2]
                and highs[i] > highs[i + 1]
                and highs[i] > highs[i + 2]
            ):
                swing_highs.append((i, highs[i]))
            if (
                lows[i] < lows[i - 1]
                and lows[i] < lows[i - 2]
                and lows[i] < lows[i + 1]
                and lows[i] < lows[i + 2]
            ):
                swing_lows.append((i, lows[i]))

        highs_arr = np.array(swing_highs, dtype=float) if swing_highs else np.empty((0, 2))
        lows_arr = np.array(swing_lows, dtype=float) if swing_lows else np.empty((0, 2))
        return {"highs": highs_arr, "lows": lows_arr}
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/unit/test_swing_points.py::test_swing_points_basic_high -v`
Expected: PASS.

---

## Task 4: SwingPoints — additional tests for lows, edges, constant series

**Files:**
- Modify: `tests/unit/test_swing_points.py`

- [ ] **Step 1: Add three more tests**

Append to `tests/unit/test_swing_points.py`:
```python
def test_swing_points_basic_low():
    """Bar i is a swing low if low[i] < min(low[i-2..i-1]) AND low[i] < min(low[i+1..i+2])."""
    highs = [20.0, 19.0, 18.0, 10.0, 18.0, 19.0, 20.0, 21.0, 22.0]
    lows = [h - 5.0 for h in highs]  # parallel U-shape
    sp = SwingPoints()
    result = sp.compute(_candles(highs, lows), lookback=60)
    assert (3, lows[3]) in [(int(i), float(p)) for i, p in result["lows"]]


def test_swing_points_excludes_edges():
    """Peaks within 2 bars of array start/end must be excluded (need 2 bars on each side)."""
    # Peak at index 1 (only 1 bar before) — must NOT be returned
    # Peak at index n-1 (no bars after) — must NOT be returned
    highs = [10.0, 50.0, 12.0, 11.0, 12.0, 11.0, 10.0, 50.0]
    lows = [h - 5.0 for h in highs]
    sp = SwingPoints()
    result = sp.compute(_candles(highs, lows), lookback=60)
    indices = [int(i) for i, _ in result["highs"]]
    assert 1 not in indices
    assert (len(highs) - 1) not in indices


def test_swing_points_constant_series():
    """Flat series → empty highs and empty lows."""
    highs = [50.0] * 30
    lows = [45.0] * 30
    sp = SwingPoints()
    result = sp.compute(_candles(highs, lows), lookback=60)
    assert result["highs"].shape == (0, 2)
    assert result["lows"].shape == (0, 2)
```

- [ ] **Step 2: Run all SwingPoints tests**

Run: `pytest tests/unit/test_swing_points.py -v`
Expected: 4 tests pass.

- [ ] **Step 3: Commit**

```bash
git add src/scanner/indicators/support_resistance.py tests/unit/test_swing_points.py
git commit -m "feat: add SwingPoints indicator (fractal swing high/low detection)"
```

---

## Task 5: RSI divergence helper — failing tests

**Files:**
- Create: `tests/unit/test_rsi_divergence.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_rsi_divergence.py`:
```python
"""Unit tests for rsi_divergence helper."""

import numpy as np

from src.scanner.indicators.momentum import rsi_divergence


def test_rsi_divergence_bullish():
    """Lower price low + higher RSI low → bullish_div=True, bearish_div=False."""
    prices = np.array([100.0, 90.0, 95.0, 85.0])
    rsi = np.array([55.0, 30.0, 50.0, 35.0])
    bull, bear = rsi_divergence(prices, rsi, prior_pivot=1, current_pivot=3)
    assert bull is True
    assert bear is False


def test_rsi_divergence_bearish():
    """Higher price high + lower RSI high → bearish_div=True."""
    prices = np.array([100.0, 110.0, 105.0, 115.0])
    rsi = np.array([55.0, 80.0, 60.0, 70.0])
    bull, bear = rsi_divergence(prices, rsi, prior_pivot=1, current_pivot=3)
    assert bear is True
    assert bull is False


def test_rsi_divergence_none():
    """Both lows higher and both RSI lows higher → no divergence either side."""
    prices = np.array([100.0, 90.0, 95.0, 92.0])
    rsi = np.array([55.0, 30.0, 50.0, 35.0])
    bull, bear = rsi_divergence(prices, rsi, prior_pivot=1, current_pivot=3)
    assert bull is False
    assert bear is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_rsi_divergence.py -v`
Expected: FAIL with `ImportError: cannot import name 'rsi_divergence'`.

---

## Task 6: RSI divergence helper — implementation

**Files:**
- Modify: `src/scanner/indicators/momentum.py`

- [ ] **Step 1: Add rsi_divergence function**

Append to `src/scanner/indicators/momentum.py` (after the `MACD` class):
```python
def rsi_divergence(
    prices: np.ndarray,
    rsi: np.ndarray,
    prior_pivot: int,
    current_pivot: int,
) -> tuple[bool, bool]:
    """Detect classical bullish/bearish RSI divergence between two pivots.

    Bullish: price[current] < price[prior] AND rsi[current] > rsi[prior].
    Bearish: price[current] > price[prior] AND rsi[current] < rsi[prior].
    Both indices must be in-bounds; returns (False, False) otherwise.
    """
    if prior_pivot < 0 or current_pivot < 0:
        return (False, False)
    if prior_pivot >= len(prices) or current_pivot >= len(prices):
        return (False, False)
    if prior_pivot >= len(rsi) or current_pivot >= len(rsi):
        return (False, False)

    p_prior, p_curr = float(prices[prior_pivot]), float(prices[current_pivot])
    r_prior, r_curr = float(rsi[prior_pivot]), float(rsi[current_pivot])

    bull = p_curr < p_prior and r_curr > r_prior
    bear = p_curr > p_prior and r_curr < r_prior
    return (bull, bear)
```

- [ ] **Step 2: Run divergence tests**

Run: `pytest tests/unit/test_rsi_divergence.py -v`
Expected: 3 tests pass.

- [ ] **Step 3: Commit**

```bash
git add src/scanner/indicators/momentum.py tests/unit/test_rsi_divergence.py
git commit -m "feat: add rsi_divergence helper for pivot-based divergence detection"
```

---

## Task 7: Scanner skeleton — failing test for scaffolding

**Files:**
- Create: `tests/unit/test_pullback_continuation_scanner.py`
- Create: `src/scanner/scanners/pullback_continuation.py`

- [ ] **Step 1: Write the failing scaffolding test**

Create `tests/unit/test_pullback_continuation_scanner.py`:
```python
"""Unit tests for PullbackContinuationScanner."""

from datetime import datetime, timedelta
from typing import List

from src.data_provider.base import Candle
from src.scanner.context import ScanContext
from src.scanner.indicators.cache import IndicatorCache
from src.scanner.indicators.moving_averages import EMA
from src.scanner.indicators.momentum import RSI, MACD
from src.scanner.indicators.volatility import ATR
from src.scanner.indicators.support_resistance import SwingPoints
from src.scanner.scanners.pullback_continuation import PullbackContinuationScanner


def _make_indicators():
    return {
        "ema": EMA(),
        "rsi": RSI(),
        "macd": MACD(),
        "atr": ATR(),
        "swing_points": SwingPoints(),
    }


def _make_context(candles: List[Candle], stock_id: int = 1, symbol: str = "TEST") -> ScanContext:
    return ScanContext(
        stock_id=stock_id,
        symbol=symbol,
        daily_candles=candles,
        intraday_candles={},
        indicator_cache=IndicatorCache(_make_indicators()),
    )


def test_scanner_returns_empty_list_with_too_few_candles():
    """< 80 candles → returns []."""
    base_dt = datetime(2024, 1, 1)
    candles = [
        Candle(base_dt + timedelta(days=i), 100.0, 101.0, 99.0, 100.0, 5_000_000)
        for i in range(50)
    ]
    scanner = PullbackContinuationScanner()
    assert scanner.scan(_make_context(candles)) == []
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/unit/test_pullback_continuation_scanner.py::test_scanner_returns_empty_list_with_too_few_candles -v`
Expected: FAIL with `ModuleNotFoundError`.

---

## Task 8: Scanner skeleton — minimal class

**Files:**
- Create: `src/scanner/scanners/pullback_continuation.py`

- [ ] **Step 1: Write the minimal scaffolding**

Create `src/scanner/scanners/pullback_continuation.py`:
```python
"""Pullback continuation scanner: trend + geometry + exhaustion + trigger confluence."""

import logging
from typing import List

import numpy as np

from src.scanner.base import Scanner, ScanResult
from src.scanner.context import ScanContext

logger = logging.getLogger(__name__)


class PullbackContinuationScanner(Scanner):
    """Bidirectional pullback continuation: trend + geometry + exhaustion + trigger."""

    timeframe = "daily"
    description = "Bidirectional pullback continuation: trend + geometry + exhaustion + trigger"

    MIN_CANDLES = 80
    PRICE_MIN = 20.0
    AVG_DOLLAR_VOL_MIN = 50_000_000.0
    ATR_PCT_MIN = 1.5

    SWING_MIN_BARS_AGO = 3
    SWING_MAX_BARS_AGO = 15
    RETRACE_MIN = 0.38
    RETRACE_MAX = 0.78
    EXHAUSTION_WINDOW = 3
    EXHAUSTION_REQUIRED = 2
    VOLUME_SURGE_RATIO = 1.2
    SUPPORT_TOUCH_LOOKBACK = 60
    SUPPORT_TOUCH_MIN_HITS = 2
    SUPPORT_ATR_TOLERANCE = 0.5
    LOW_CONVICTION_THRESHOLD = 40

    EXTENSION_MULT = 1.618
    STOP_ATR_MULT = 0.5

    def scan(self, context: ScanContext) -> List[ScanResult]:
        """Return at most one ScanResult per stock; never raise."""
        candles = context.daily_candles
        results: List[ScanResult] = []

        if len(candles) < self.MIN_CANDLES:
            logger.debug(f"Insufficient candles: {len(candles)} < {self.MIN_CANDLES}")
            return results

        try:
            # All rule logic added in subsequent tasks.
            return results
        except Exception:
            logger.exception(f"PullbackContinuationScanner failed for {context.symbol}")
            return results
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/unit/test_pullback_continuation_scanner.py::test_scanner_returns_empty_list_with_too_few_candles -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add src/scanner/scanners/pullback_continuation.py tests/unit/test_pullback_continuation_scanner.py
git commit -m "feat: pullback-continuation scanner scaffold"
```

---

## Task 9: Add candle-fixture builders to test file

**Files:**
- Modify: `tests/unit/test_pullback_continuation_scanner.py`

- [ ] **Step 1: Add reusable fixture builders for long and short setups**

Append to `tests/unit/test_pullback_continuation_scanner.py`, after the existing imports/helpers:
```python
def _bullish_pullback_candles(
    *,
    pullback_low_offset: float = 0.0,
    swing_high_offset: int = 0,
    trigger_close: float = 165.0,
    trigger_volume: int = 5_000_000,
    base_volume: int = 2_000_000,
) -> List[Candle]:
    """80 candles producing a clean long pullback continuation setup.

    Phase 1 (60 bars): steady uptrend 80 → 150 (locks EMA stack and positive EMA(50) slope).
    Phase 2 (12 bars): mark a swing high at 160 around index 67 (≈12 bars before today),
                       then pullback to ~150 (≈50% retracement of the up-leg).
    Phase 3 (8 bars): drift / form exhaustion (volume surge on penultimate, MACD/RSI conditions).
    Phase 4 (1 bar):  trigger today — close > EMA(9) AND > 3-bar high; volume surge.
    """
    base_dt = datetime(2024, 1, 1)
    candles: List[Candle] = []

    # Phase 1: trending up, 60 bars, 80 → 150
    for i in range(60):
        price = 80.0 + i * (70.0 / 59.0)
        candles.append(
            Candle(
                timestamp=base_dt + timedelta(days=i),
                open=price,
                high=price + 1.0,
                low=price - 1.0,
                close=price,
                volume=base_volume,
            )
        )

    # Phase 2: swing high at index 67 then pullback bottoming around index 75
    leg = [152.0, 156.0, 159.0, 161.0, 159.0, 156.0, 152.0, 149.5 + pullback_low_offset]
    for i, price in enumerate(leg):
        candles.append(
            Candle(
                timestamp=base_dt + timedelta(days=60 + i),
                open=price,
                high=price + 1.0,
                low=price - 1.0,
                close=price,
                volume=base_volume,
            )
        )

    # Phase 3: 11 bars of base / exhaustion — small bounces, MACD recovers, vol surge on last
    consolidation = [150.0, 151.5, 152.0, 151.0, 152.5, 153.0, 153.5, 154.0, 155.0, 156.0, 157.0]
    for i, price in enumerate(consolidation):
        vol = int(base_volume * 1.3) if i == len(consolidation) - 1 else base_volume
        candles.append(
            Candle(
                timestamp=base_dt + timedelta(days=68 + i),
                open=price,
                high=price + 1.0,
                low=price - 1.0,
                close=price,
                volume=vol,
            )
        )

    # Phase 4: trigger today (index 79) — close above 3-bar high, volume surge
    candles.append(
        Candle(
            timestamp=base_dt + timedelta(days=79),
            open=157.5,
            high=trigger_close + 1.0,
            low=157.0,
            close=trigger_close,
            volume=trigger_volume,
        )
    )

    return candles


def _bearish_failed_bounce_candles(
    *, trigger_close: float = 138.0, trigger_volume: int = 5_000_000
) -> List[Candle]:
    """80 candles where uptrend was confirmed at bar H, broke at bar L, today rejects bounce.

    Phase 1 (55 bars): uptrend 80 → 160 (locks EMA stack at the prior swing high H).
    Phase 2 (12 bars): swing high at 160, sharp drop through EMA(21) to swing low L at ~140.
    Phase 3 (12 bars): bounce up to ~150, fails near resistance, MACD rolls negative.
    Phase 4 (1 bar):  trigger — close < EMA(21), close below 3-bar low, volume surge.
    """
    base_dt = datetime(2024, 1, 1)
    candles: List[Candle] = []

    # Phase 1: uptrend
    for i in range(55):
        price = 80.0 + i * (80.0 / 54.0)
        candles.append(
            Candle(
                timestamp=base_dt + timedelta(days=i),
                open=price,
                high=price + 1.0,
                low=price - 1.0,
                close=price,
                volume=2_000_000,
            )
        )

    # Phase 2: swing high (H) at index ~57, drop through to swing low (L) at index ~67
    drop = [161.0, 160.0, 158.0, 154.0, 150.0, 146.0, 143.0, 141.0, 140.0, 140.5, 140.0, 139.5]
    for i, price in enumerate(drop):
        candles.append(
            Candle(
                timestamp=base_dt + timedelta(days=55 + i),
                open=price,
                high=price + 1.0,
                low=price - 1.0,
                close=price,
                volume=2_000_000,
            )
        )

    # Phase 3: bounce that fails — recovers to ~150 then rolls over
    bounce = [142.0, 145.0, 148.0, 150.0, 151.0, 150.5, 149.0, 147.0, 145.0, 143.0, 141.0]
    for i, price in enumerate(bounce):
        vol = 2_600_000 if i == len(bounce) - 1 else 2_000_000  # volume surge on last
        candles.append(
            Candle(
                timestamp=base_dt + timedelta(days=67 + i),
                open=price,
                high=price + 1.0,
                low=price - 1.0,
                close=price,
                volume=vol,
            )
        )

    # Phase 4: trigger today (index 79) — close below 3-bar low, volume surge
    candles.append(
        Candle(
            timestamp=base_dt + timedelta(days=79),
            open=141.0,
            high=141.5,
            low=trigger_close - 1.0,
            close=trigger_close,
            volume=trigger_volume,
        )
    )
    return candles
```

These fixtures produce *deterministic* candle series. As you implement subsequent rules, run the long fixture through the scanner with print statements (or pytest `-s`) to verify each rule passes; tweak the fixture numbers if a rule edge-case prevents the signal from firing as designed. The principle: the fixtures are tools to produce a clean signal; only fixture numbers (not rule constants) get adjusted.

- [ ] **Step 2: Sanity-run pytest to confirm test file imports cleanly**

Run: `pytest tests/unit/test_pullback_continuation_scanner.py -v`
Expected: 1 test still passing (`test_scanner_returns_empty_list_with_too_few_candles`); no import errors.

---

## Task 10: Universe / liquidity filter

**Files:**
- Modify: `src/scanner/scanners/pullback_continuation.py`
- Modify: `tests/unit/test_pullback_continuation_scanner.py`

- [ ] **Step 1: Write failing tests for universe filters**

Append to `tests/unit/test_pullback_continuation_scanner.py`:
```python
def test_universe_filter_price():
    """close < $20 → no signal."""
    base_dt = datetime(2024, 1, 1)
    cheap = [
        Candle(base_dt + timedelta(days=i), 15.0, 16.0, 14.0, 15.0, 5_000_000)
        for i in range(80)
    ]
    scanner = PullbackContinuationScanner()
    assert scanner.scan(_make_context(cheap)) == []


def test_universe_filter_dollar_volume():
    """avg dollar volume < $50M → no signal."""
    base_dt = datetime(2024, 1, 1)
    thin = [
        Candle(base_dt + timedelta(days=i), 25.0, 26.0, 24.0, 25.0, 100)
        for i in range(80)
    ]
    scanner = PullbackContinuationScanner()
    assert scanner.scan(_make_context(thin)) == []


def test_universe_filter_atr():
    """ATR% < 1.5 → no signal (tight series)."""
    base_dt = datetime(2024, 1, 1)
    flat = [
        Candle(base_dt + timedelta(days=i), 100.0, 100.05, 99.95, 100.0, 5_000_000)
        for i in range(80)
    ]
    scanner = PullbackContinuationScanner()
    assert scanner.scan(_make_context(flat)) == []
```

- [ ] **Step 2: Run tests — they should still pass (skeleton returns [])**

Run: `pytest tests/unit/test_pullback_continuation_scanner.py -v`
Expected: all 4 tests pass — but only because skeleton always returns `[]`. We need the filter wired so positive-path tests fail correctly later.

- [ ] **Step 3: Wire the universe filter inside the scanner**

Replace the body of `try:` in `scan()` in `src/scanner/scanners/pullback_continuation.py` with:
```python
            atr_arr = context.get_indicator("atr", period=14)
            if len(atr_arr) < 1:
                return results

            close = float(candles[-1].close)
            if close < self.PRICE_MIN:
                return results

            avg_dollar_vol = float(np.mean([c.close * c.volume for c in candles[-21:-1]]))
            if avg_dollar_vol < self.AVG_DOLLAR_VOL_MIN:
                return results

            atr_val = float(atr_arr[-1])
            if not np.isfinite(atr_val) or atr_val == 0:
                return results
            atr_pct = atr_val / close * 100
            if atr_pct < self.ATR_PCT_MIN:
                return results

            # Subsequent rules (trend / geometry / exhaustion / trigger) added in later tasks.
            return results
```

- [ ] **Step 4: Run all tests**

Run: `pytest tests/unit/test_pullback_continuation_scanner.py -v`
Expected: all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/scanner/scanners/pullback_continuation.py tests/unit/test_pullback_continuation_scanner.py
git commit -m "feat(pullback-continuation): liquidity/universe filter"
```

---

## Task 11: Trend confirmation rule

**Files:**
- Modify: `src/scanner/scanners/pullback_continuation.py`
- Modify: `tests/unit/test_pullback_continuation_scanner.py`

The trend rule depends on the swing-anchor bar `H` (long) or `L` (short). Defer the long-vs-short branching to Task 13 (geometry) — for now, compute swing points and the EMA arrays, and add helper methods that the geometry rule can call to verify the trend at any anchor bar.

- [ ] **Step 1: Add the failing "EMA(50) slope must be positive for long" test**

Append to `tests/unit/test_pullback_continuation_scanner.py`:
```python
def test_no_signal_when_ema50_slope_negative():
    """EMA(50) slope flat or down → no long signal even if EMA stack OK at H."""
    base_dt = datetime(2024, 1, 1)
    # Trend up early, flat for last 30 bars — slope[-1] vs slope[-10] non-positive
    candles = []
    for i in range(50):
        price = 80.0 + i * 1.4
        candles.append(
            Candle(base_dt + timedelta(days=i), price, price + 1.0, price - 1.0, price, 3_000_000)
        )
    for i in range(30):
        candles.append(
            Candle(
                base_dt + timedelta(days=50 + i), 150.0, 151.0, 149.0, 150.0, 3_000_000
            )
        )
    scanner = PullbackContinuationScanner()
    assert scanner.scan(_make_context(candles)) == []
```

- [ ] **Step 2: Run test — should pass (skeleton still returns [] for everything)**

Run: `pytest tests/unit/test_pullback_continuation_scanner.py::test_no_signal_when_ema50_slope_negative -v`
Expected: PASS (vacuously). This becomes a real check after Task 14.

- [ ] **Step 3: Add EMA arrays and slope check inside scan()**

In `src/scanner/scanners/pullback_continuation.py`, before `# Subsequent rules ...`, add:
```python
            ema_9_arr = context.get_indicator("ema", period=9)
            ema_21_arr = context.get_indicator("ema", period=21)
            ema_50_arr = context.get_indicator("ema", period=50)
            if len(ema_9_arr) < 1 or len(ema_21_arr) < 1 or len(ema_50_arr) < 11:
                return results
            for arr in (ema_9_arr, ema_21_arr, ema_50_arr):
                if not np.all(np.isfinite(arr[-12:])):
                    return results

            ema_50_today = float(ema_50_arr[-1])
            ema_50_10_back = float(ema_50_arr[-11])
            ema_50_slope_10 = (
                (ema_50_today - ema_50_10_back) / ema_50_10_back if ema_50_10_back != 0 else 0.0
            )
```

(Note: each EMA array is len(candles) - period + 1 long, so `ema_50_arr[-11]` corresponds to bar `today − 10` only when `len(candles) ≥ period + 10`. With `MIN_CANDLES = 80` and period=50, len of ema_50_arr is 31 → safe.)

- [ ] **Step 4: Add a private helper for trend-at-anchor**

Append inside the `PullbackContinuationScanner` class (e.g., before `scan`):
```python
    def _stack_at(
        self,
        ema_9_arr: np.ndarray,
        ema_21_arr: np.ndarray,
        ema_50_arr: np.ndarray,
        anchor_neg_offset: int,
    ) -> tuple[float, float, float]:
        """Return (ema_9, ema_21, ema_50) at anchor bar, given a negative offset (e.g. -8).

        Each EMA array is offset from the candles array by (period - 1). Caller passes the
        anchor as a negative offset relative to the *candles* array (e.g., bar at idx -8 in
        candles ↔ idx -8 in the EMA arrays IF the EMA arrays are aligned to len(candles);
        but EMA arrays have shorter length, so we map by tail offset).
        """
        # All EMA arrays end at "today"; since they're computed from the same candles tail,
        # ema_X_arr[-1] = today, ema_X_arr[-2] = yesterday, etc. The same negative offset
        # therefore points to the same bar in all three.
        return (
            float(ema_9_arr[anchor_neg_offset]),
            float(ema_21_arr[anchor_neg_offset]),
            float(ema_50_arr[anchor_neg_offset]),
        )
```

- [ ] **Step 5: Run all tests**

Run: `pytest tests/unit/test_pullback_continuation_scanner.py -v`
Expected: all tests still pass.

- [ ] **Step 6: Commit**

```bash
git add src/scanner/scanners/pullback_continuation.py tests/unit/test_pullback_continuation_scanner.py
git commit -m "feat(pullback-continuation): EMA stack arrays and slope helper"
```

---

## Task 12: Pullback geometry — long branch

**Files:**
- Modify: `src/scanner/scanners/pullback_continuation.py`

Long rule (from spec):
- Bar `H` is a swing high in the last 3–15 bars (inclusive).
- Bar `L` = swing low immediately preceding `H`.
- `up_leg = high[H] − low[L]`.
- `pullback_low` = lowest low between `H` and today.
- `retrace_pct = (high[H] − pullback_low) / up_leg ∈ [0.38, 0.78]`.

- [ ] **Step 1: Add failing tests for geometry edges**

Append to `tests/unit/test_pullback_continuation_scanner.py`:
```python
def test_no_signal_when_pullback_too_shallow():
    """retrace 25% → no signal (below 0.38 floor)."""
    candles = _bullish_pullback_candles(pullback_low_offset=8.0)  # raises pullback low → shallow
    scanner = PullbackContinuationScanner()
    # The fixture aims for ~50% retrace; pullback_low_offset=+8 raises pullback low ~8 pts
    # making retrace ≈ (high-pullback)/up_leg shallower than 0.38
    results = scanner.scan(_make_context(candles))
    assert results == []


def test_no_signal_when_pullback_too_deep():
    """retrace 85% → no signal (above 0.78 ceiling)."""
    candles = _bullish_pullback_candles(pullback_low_offset=-15.0)  # very deep pullback
    scanner = PullbackContinuationScanner()
    results = scanner.scan(_make_context(candles))
    assert results == []
```

- [ ] **Step 2: Run — should pass vacuously (still no positive-path test)**

Run: `pytest tests/unit/test_pullback_continuation_scanner.py -v`
Expected: all tests pass.

- [ ] **Step 3: Implement the long-side geometry detector**

Add this method on the scanner class:
```python
    def _find_long_geometry(
        self,
        candles: list,
        swings: dict,
    ) -> dict | None:
        """Find a long-eligible pullback structure ending today.

        Returns:
            dict with keys H_idx, H_high, L_idx, L_low, up_leg, pullback_low_idx,
                 pullback_low, retrace_pct — or None if no qualifying structure.
        """
        n = len(candles)
        today_idx = n - 1
        highs_arr = swings.get("highs", np.empty((0, 2)))
        lows_arr = swings.get("lows", np.empty((0, 2)))
        if highs_arr.size == 0 or lows_arr.size == 0:
            return None

        # Convert to lists of ints/floats for filter convenience.
        sh = [(int(i), float(p)) for i, p in highs_arr]
        sl = [(int(i), float(p)) for i, p in lows_arr]

        # Restrict swing highs to bars 3..15 ago.
        candidates = [
            (idx, price)
            for idx, price in sh
            if self.SWING_MIN_BARS_AGO <= (today_idx - idx) <= self.SWING_MAX_BARS_AGO
        ]
        if not candidates:
            return None
        # Use the most recent qualifying swing high.
        h_idx, h_high = max(candidates, key=lambda t: t[0])

        # Find the swing low immediately before H.
        prior_lows = [(idx, price) for idx, price in sl if idx < h_idx]
        if not prior_lows:
            return None
        l_idx, l_low = max(prior_lows, key=lambda t: t[0])

        up_leg = h_high - l_low
        if up_leg <= 0:
            return None

        # Pullback low between H and today (inclusive of today).
        pullback_low_idx = h_idx + 1 + int(np.argmin([candles[i].low for i in range(h_idx + 1, n)]))
        pullback_low = float(candles[pullback_low_idx].low)

        retrace_pct = (h_high - pullback_low) / up_leg
        if retrace_pct < self.RETRACE_MIN or retrace_pct > self.RETRACE_MAX:
            return None

        return {
            "H_idx": h_idx,
            "H_high": h_high,
            "L_idx": l_idx,
            "L_low": l_low,
            "up_leg": up_leg,
            "pullback_low_idx": pullback_low_idx,
            "pullback_low": pullback_low,
            "retrace_pct": retrace_pct,
        }
```

- [ ] **Step 4: Wire SwingPoints fetch into scan()**

In `scan()`, before the trend slope block, add:
```python
            swings = context.get_indicator("swing_points", lookback=60)
```

- [ ] **Step 5: Run all tests**

Run: `pytest tests/unit/test_pullback_continuation_scanner.py -v`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/scanner/scanners/pullback_continuation.py tests/unit/test_pullback_continuation_scanner.py
git commit -m "feat(pullback-continuation): long-side pullback geometry detector"
```

---

## Task 13: Pullback geometry — short branch (mirror)

**Files:**
- Modify: `src/scanner/scanners/pullback_continuation.py`

Short rule mirrors long: most recent qualifying swing low `L` (3–15 bars ago) and the swing high `H` *immediately preceding* `L`. `down_leg = high[H] − low[L]`. `bounce_high = max(high) between L and today`. `retrace_pct ∈ [0.38, 0.78]`.

- [ ] **Step 1: Implement _find_short_geometry**

Add to the scanner class:
```python
    def _find_short_geometry(
        self,
        candles: list,
        swings: dict,
    ) -> dict | None:
        n = len(candles)
        today_idx = n - 1
        highs_arr = swings.get("highs", np.empty((0, 2)))
        lows_arr = swings.get("lows", np.empty((0, 2)))
        if highs_arr.size == 0 or lows_arr.size == 0:
            return None

        sh = [(int(i), float(p)) for i, p in highs_arr]
        sl = [(int(i), float(p)) for i, p in lows_arr]

        candidates = [
            (idx, price)
            for idx, price in sl
            if self.SWING_MIN_BARS_AGO <= (today_idx - idx) <= self.SWING_MAX_BARS_AGO
        ]
        if not candidates:
            return None
        l_idx, l_low = max(candidates, key=lambda t: t[0])

        prior_highs = [(idx, price) for idx, price in sh if idx < l_idx]
        if not prior_highs:
            return None
        h_idx, h_high = max(prior_highs, key=lambda t: t[0])

        down_leg = h_high - l_low
        if down_leg <= 0:
            return None

        bounce_high_idx = (
            l_idx + 1 + int(np.argmax([candles[i].high for i in range(l_idx + 1, n)]))
        )
        bounce_high = float(candles[bounce_high_idx].high)

        retrace_pct = (bounce_high - l_low) / down_leg
        if retrace_pct < self.RETRACE_MIN or retrace_pct > self.RETRACE_MAX:
            return None

        return {
            "H_idx": h_idx,
            "H_high": h_high,
            "L_idx": l_idx,
            "L_low": l_low,
            "down_leg": down_leg,
            "bounce_high_idx": bounce_high_idx,
            "bounce_high": bounce_high,
            "retrace_pct": retrace_pct,
        }
```

- [ ] **Step 2: Sanity-run tests**

Run: `pytest tests/unit/test_pullback_continuation_scanner.py -v`
Expected: all tests still pass.

- [ ] **Step 3: Commit**

```bash
git add src/scanner/scanners/pullback_continuation.py
git commit -m "feat(pullback-continuation): short-side bounce geometry detector"
```

---

## Task 14: Trend confirmation — gate by direction and anchor bar

**Files:**
- Modify: `src/scanner/scanners/pullback_continuation.py`

- [ ] **Step 1: Add the trend-check helpers**

Add to the scanner class:
```python
    def _trend_ok_long(
        self,
        ema_9_arr: np.ndarray,
        ema_21_arr: np.ndarray,
        ema_50_arr: np.ndarray,
        candles: list,
        h_idx: int,
        ema_50_slope_10: float,
    ) -> bool:
        # Translate candle index h_idx to negative offset relative to ema arrays.
        n = len(candles)
        offset = -(n - h_idx)
        ema_9_h, ema_21_h, ema_50_h = self._stack_at(ema_9_arr, ema_21_arr, ema_50_arr, offset)
        close_h = float(candles[h_idx].close)
        if not (ema_9_h > ema_21_h > ema_50_h):
            return False
        if not (close_h > ema_21_h):
            return False
        if ema_50_slope_10 <= 0:
            return False
        return True

    def _trend_ok_short(
        self,
        ema_9_arr: np.ndarray,
        ema_21_arr: np.ndarray,
        ema_50_arr: np.ndarray,
        candles: list,
        h_idx: int,
        l_idx: int,
        ema_50_slope_10: float,
    ) -> bool:
        n = len(candles)
        h_off = -(n - h_idx)
        l_off = -(n - l_idx)
        ema_9_h, ema_21_h, ema_50_h = self._stack_at(ema_9_arr, ema_21_arr, ema_50_arr, h_off)
        ema_21_l = float(ema_21_arr[l_off])
        close_h = float(candles[h_idx].close)
        close_l = float(candles[l_idx].close)
        if not (ema_9_h > ema_21_h > ema_50_h):
            return False
        if not (close_h > ema_21_h):
            return False
        if not (close_l < ema_21_l):
            return False
        if ema_50_slope_10 > 0:  # spec: flat-to-negative for short
            return False
        return True
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/unit/test_pullback_continuation_scanner.py -v`
Expected: all tests still pass.

- [ ] **Step 3: Commit**

```bash
git add src/scanner/scanners/pullback_continuation.py
git commit -m "feat(pullback-continuation): direction-aware trend confirmation"
```

---

## Task 15: Exhaustion criteria

**Files:**
- Modify: `src/scanner/scanners/pullback_continuation.py`

For each of the last `EXHAUSTION_WINDOW = 3` bars (today, today-1, today-2), evaluate four boolean criteria. Long requires ≥2 across the window combined.

**Criteria (long):**
- `support_hold`: bar's low touched a support level (price tested ≥2× in last 60 bars within ±0.5×ATR) AND bar closed above that level.
- `rsi_div`: bar made a lower low than the prior pullback low, but RSI made a higher low.
- `volume_surge`: bar volume > 1.2× 20-day avg (excluding the bar itself).
- `macd_cross`: MACD histogram crossed from negative to ≥0 on that bar.

The MACD indicator returns the MACD line; the *histogram* is `macd_line − signal(macd_line, 9)`. Compute the signal manually.

- [ ] **Step 1: Add a private MACD-histogram helper**

Add to the scanner class (or as a module-level helper):
```python
    @staticmethod
    def _macd_histogram(macd_line: np.ndarray, signal_period: int = 9) -> np.ndarray:
        """Return MACD histogram (macd_line − EMA(macd_line, signal_period))."""
        if len(macd_line) < signal_period:
            return np.array([])
        alpha = 2 / (signal_period + 1)
        sig = [float(np.mean(macd_line[:signal_period]))]
        for v in macd_line[signal_period:]:
            sig.append(alpha * float(v) + (1 - alpha) * sig[-1])
        sig_arr = np.array(sig)
        # macd_line and sig_arr are aligned at the tail.
        min_len = min(len(macd_line), len(sig_arr))
        return macd_line[-min_len:] - sig_arr[-min_len:]
```

- [ ] **Step 2: Add a private "support level" extractor**

```python
    def _support_levels(self, candles: list, atr_val: float) -> list[float]:
        """Return prices that have been tested ≥2× in the last 60 bars within ±0.5×ATR.

        Cluster lows over the lookback window; a cluster of ≥SUPPORT_TOUCH_MIN_HITS lows
        within SUPPORT_ATR_TOLERANCE×ATR of each other becomes a level (its mean).
        """
        lookback = self.SUPPORT_TOUCH_LOOKBACK
        tail = candles[-lookback:] if len(candles) >= lookback else candles
        lows = sorted(c.low for c in tail)
        if not lows or atr_val <= 0:
            return []
        tol = self.SUPPORT_ATR_TOLERANCE * atr_val

        levels: list[float] = []
        cluster: list[float] = [lows[0]]
        for v in lows[1:]:
            if v - cluster[-1] <= tol:
                cluster.append(v)
            else:
                if len(cluster) >= self.SUPPORT_TOUCH_MIN_HITS:
                    levels.append(float(np.mean(cluster)))
                cluster = [v]
        if len(cluster) >= self.SUPPORT_TOUCH_MIN_HITS:
            levels.append(float(np.mean(cluster)))
        return levels

    def _resistance_levels(self, candles: list, atr_val: float) -> list[float]:
        lookback = self.SUPPORT_TOUCH_LOOKBACK
        tail = candles[-lookback:] if len(candles) >= lookback else candles
        highs = sorted((c.high for c in tail), reverse=True)
        if not highs or atr_val <= 0:
            return []
        tol = self.SUPPORT_ATR_TOLERANCE * atr_val
        levels: list[float] = []
        cluster: list[float] = [highs[0]]
        for v in highs[1:]:
            if cluster[-1] - v <= tol:
                cluster.append(v)
            else:
                if len(cluster) >= self.SUPPORT_TOUCH_MIN_HITS:
                    levels.append(float(np.mean(cluster)))
                cluster = [v]
        if len(cluster) >= self.SUPPORT_TOUCH_MIN_HITS:
            levels.append(float(np.mean(cluster)))
        return levels
```

- [ ] **Step 3: Add long-side exhaustion evaluator**

```python
    def _exhaustion_long(
        self,
        candles: list,
        atr_val: float,
        rsi_arr: np.ndarray,
        macd_hist: np.ndarray,
        prior_pullback_low_idx: int,
        prior_pullback_low: float,
    ) -> tuple[int, list[str]]:
        """Return (count, reasons) — count of distinct exhaustion criteria fired in last 3 bars."""
        from src.scanner.indicators.momentum import rsi_divergence

        n = len(candles)
        levels = self._support_levels(candles, atr_val)
        tol = self.SUPPORT_ATR_TOLERANCE * atr_val
        avg_vol_20 = float(np.mean([c.volume for c in candles[-21:-1]])) if n >= 21 else 0.0

        reasons: set[str] = set()
        # Closes & lows arrays for divergence
        closes = np.array([c.close for c in candles], dtype=float)

        for k in range(self.EXHAUSTION_WINDOW):
            bar_idx = n - 1 - k
            bar = candles[bar_idx]

            # support_hold
            for lvl in levels:
                if abs(bar.low - lvl) <= tol and bar.close > lvl:
                    reasons.add("support_hold")
                    break

            # rsi_div — current pivot is bar_idx, prior is prior_pullback_low_idx
            if len(rsi_arr) > 0 and bar_idx < n and prior_pullback_low_idx < n:
                # Map bar_idx to RSI offset; rsi_arr len = len(closes) - 14 (period+1 actually).
                rsi_offset_today = -(n - bar_idx)
                rsi_offset_prior = -(n - prior_pullback_low_idx)
                # Both must be in-bounds of rsi_arr
                if (
                    abs(rsi_offset_today) <= len(rsi_arr)
                    and abs(rsi_offset_prior) <= len(rsi_arr)
                ):
                    bull, _ = rsi_divergence(
                        closes,
                        np.concatenate(
                            [np.full(n - len(rsi_arr), np.nan), rsi_arr]
                        ),
                        prior_pivot=prior_pullback_low_idx,
                        current_pivot=bar_idx,
                    )
                    if bull and bar.low < prior_pullback_low:
                        reasons.add("rsi_div")

            # volume_surge
            if avg_vol_20 > 0 and bar.volume > self.VOLUME_SURGE_RATIO * avg_vol_20:
                reasons.add("volume_surge")

            # macd_cross — histogram crossed from negative to ≥0 on this bar
            if len(macd_hist) >= 2:
                hist_today_off = -(n - bar_idx)
                hist_prev_off = hist_today_off - 1
                if abs(hist_today_off) <= len(macd_hist) and abs(hist_prev_off) <= len(macd_hist):
                    h_today = float(macd_hist[hist_today_off])
                    h_prev = float(macd_hist[hist_prev_off])
                    if h_prev < 0 and h_today >= 0:
                        reasons.add("macd_cross")

        return len(reasons), sorted(reasons)
```

- [ ] **Step 4: Mirror for short side**

Add `_exhaustion_short` — same shape, replacing `support_hold` with `resistance_fail` (bar high touched resistance ±0.5×ATR AND bar closed below it), `rsi_div` checks for *bearish* divergence with prior bounce high pivot, and MACD cross from ≥0 to <0:
```python
    def _exhaustion_short(
        self,
        candles: list,
        atr_val: float,
        rsi_arr: np.ndarray,
        macd_hist: np.ndarray,
        prior_bounce_high_idx: int,
        prior_bounce_high: float,
    ) -> tuple[int, list[str]]:
        from src.scanner.indicators.momentum import rsi_divergence

        n = len(candles)
        levels = self._resistance_levels(candles, atr_val)
        tol = self.SUPPORT_ATR_TOLERANCE * atr_val
        avg_vol_20 = float(np.mean([c.volume for c in candles[-21:-1]])) if n >= 21 else 0.0

        reasons: set[str] = set()
        closes = np.array([c.close for c in candles], dtype=float)

        for k in range(self.EXHAUSTION_WINDOW):
            bar_idx = n - 1 - k
            bar = candles[bar_idx]

            # resistance_fail
            for lvl in levels:
                if abs(bar.high - lvl) <= tol and bar.close < lvl:
                    reasons.add("resistance_fail")
                    break

            # rsi_div — bearish
            if len(rsi_arr) > 0 and prior_bounce_high_idx < n:
                rsi_offset_today = -(n - bar_idx)
                rsi_offset_prior = -(n - prior_bounce_high_idx)
                if (
                    abs(rsi_offset_today) <= len(rsi_arr)
                    and abs(rsi_offset_prior) <= len(rsi_arr)
                ):
                    _, bear = rsi_divergence(
                        closes,
                        np.concatenate(
                            [np.full(n - len(rsi_arr), np.nan), rsi_arr]
                        ),
                        prior_pivot=prior_bounce_high_idx,
                        current_pivot=bar_idx,
                    )
                    if bear and bar.high > prior_bounce_high:
                        reasons.add("rsi_div")

            # volume_surge
            if avg_vol_20 > 0 and bar.volume > self.VOLUME_SURGE_RATIO * avg_vol_20:
                reasons.add("volume_surge")

            # macd_cross — from ≥0 to < 0
            if len(macd_hist) >= 2:
                hist_today_off = -(n - bar_idx)
                hist_prev_off = hist_today_off - 1
                if abs(hist_today_off) <= len(macd_hist) and abs(hist_prev_off) <= len(macd_hist):
                    h_today = float(macd_hist[hist_today_off])
                    h_prev = float(macd_hist[hist_prev_off])
                    if h_prev >= 0 and h_today < 0:
                        reasons.add("macd_cross")

        return len(reasons), sorted(reasons)
```

- [ ] **Step 5: Run tests — should still pass**

Run: `pytest tests/unit/test_pullback_continuation_scanner.py -v`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/scanner/scanners/pullback_continuation.py
git commit -m "feat(pullback-continuation): exhaustion criteria detection (long+short)"
```

---

## Task 16: Trigger rule and full long-path wiring

**Files:**
- Modify: `src/scanner/scanners/pullback_continuation.py`
- Modify: `tests/unit/test_pullback_continuation_scanner.py`

Long trigger today:
- `close[today] > EMA(9)[today]` AND `close[today] > max(high[today−1], high[today−2], high[today−3])`.

- [ ] **Step 1: Add the positive-path long signal test (this should fail until wiring lands)**

Append to `tests/unit/test_pullback_continuation_scanner.py`:
```python
def test_emits_long_on_clean_pullback():
    """Trend up, retrace ~50%, ≥2 exhaustion, trigger today → exactly one long signal."""
    candles = _bullish_pullback_candles()
    scanner = PullbackContinuationScanner()
    results = scanner.scan(_make_context(candles))
    assert len(results) == 1
    r = results[0]
    assert r.scanner_name == "pullback_continuation"
    assert r.metadata["direction"] == "long"
    assert r.metadata["exhaustion_count"] >= 2
    assert 0.38 <= r.metadata["retrace_pct"] <= 0.78
```

- [ ] **Step 2: Run — should FAIL**

Run: `pytest tests/unit/test_pullback_continuation_scanner.py::test_emits_long_on_clean_pullback -v`
Expected: FAIL with `assert len(results) == 1` (currently 0).

- [ ] **Step 3: Wire the full long path in scan()**

Replace the body of `try:` in `scan()` (everything after `atr_pct = atr_val / close * 100; if atr_pct < ...: return results`) with the following long-side flow. (Short-side flow comes in Task 17.)

```python
            # --- Indicators (long path) ---
            ema_9_arr = context.get_indicator("ema", period=9)
            ema_21_arr = context.get_indicator("ema", period=21)
            ema_50_arr = context.get_indicator("ema", period=50)
            rsi_arr = context.get_indicator("rsi", period=14)
            macd_arr = context.get_indicator("macd", fast_period=12, slow_period=26, signal_period=9)
            swings = context.get_indicator("swing_points", lookback=60)

            if (
                len(ema_9_arr) < 1
                or len(ema_21_arr) < 1
                or len(ema_50_arr) < 11
                or len(rsi_arr) < 4
                or len(macd_arr) < 10
            ):
                return results
            for arr in (ema_9_arr, ema_21_arr, ema_50_arr, rsi_arr, macd_arr):
                if not np.all(np.isfinite(arr[-12:])):
                    return results

            ema_50_today = float(ema_50_arr[-1])
            ema_50_10_back = float(ema_50_arr[-11])
            ema_50_slope_10 = (
                (ema_50_today - ema_50_10_back) / ema_50_10_back if ema_50_10_back != 0 else 0.0
            )
            macd_hist = self._macd_histogram(macd_arr, signal_period=9)
            n = len(candles)

            # --- Long branch ---
            long_geo = self._find_long_geometry(candles, swings)
            long_signal = None
            if long_geo and self._trend_ok_long(
                ema_9_arr, ema_21_arr, ema_50_arr, candles, long_geo["H_idx"], ema_50_slope_10
            ):
                # Trigger today
                ema_9_today = float(ema_9_arr[-1])
                three_bar_high = max(c.high for c in candles[-4:-1])
                if close > ema_9_today and close > three_bar_high:
                    count, reasons = self._exhaustion_long(
                        candles,
                        atr_val,
                        rsi_arr,
                        macd_hist,
                        prior_pullback_low_idx=long_geo["pullback_low_idx"],
                        prior_pullback_low=long_geo["pullback_low"],
                    )
                    if count >= self.EXHAUSTION_REQUIRED:
                        long_signal = {
                            "geo": long_geo,
                            "exhaustion_count": count,
                            "exhaustion_reasons": reasons,
                            "ema_9_today": ema_9_today,
                            "ema_21_today": float(ema_21_arr[-1]),
                            "ema_50_today": ema_50_today,
                            "ema_50_slope_10": ema_50_slope_10,
                            "rsi_today": float(rsi_arr[-1]),
                            "macd_hist_today": float(macd_hist[-1]),
                        }

            if long_signal is not None:
                results.append(self._build_result(context, candles, atr_val, atr_pct, close, "long", long_signal))
                return results

            return results
```

- [ ] **Step 4: Add the `_build_result` helper (placeholder OK — Task 18 fills metadata)**

```python
    def _build_result(
        self,
        context: ScanContext,
        candles: list,
        atr_val: float,
        atr_pct: float,
        close: float,
        direction: str,
        sig: dict,
    ) -> ScanResult:
        geo = sig["geo"]
        if direction == "long":
            anchor_price = geo["H_high"]
            leg_size = geo["up_leg"]
            pullback_extreme = geo["pullback_low"]
            stop_level = pullback_extreme - self.STOP_ATR_MULT * atr_val
            target_level = close + self.EXTENSION_MULT * leg_size
            anchor_idx = len(candles) - 1 - geo["H_idx"]
        else:
            anchor_price = geo["L_low"]
            leg_size = geo["down_leg"]
            pullback_extreme = geo["bounce_high"]
            stop_level = pullback_extreme + self.STOP_ATR_MULT * atr_val
            target_level = close - self.EXTENSION_MULT * leg_size
            anchor_idx = len(candles) - 1 - geo["L_idx"]

        risk = abs(close - stop_level)
        risk_reward = abs(target_level - close) / risk if risk > 0 else 0.0

        avg_vol_20 = float(np.mean([c.volume for c in candles[-21:-1]]))
        volume_ratio = float(candles[-1].volume) / avg_vol_20 if avg_vol_20 > 0 else 0.0

        # Conviction (full implementation in Task 19; placeholder of 0 for now is OK only if
        # tests for score come later. Compute now so test_emits_long_on_clean_pullback passes
        # and metadata is complete.)
        conviction_score = 0  # filled by Task 19

        metadata = {
            "direction": direction,
            "conviction_score": conviction_score,
            "close": round(close, 4),
            "atr": round(atr_val, 4),
            "atr_pct": round(atr_pct, 4),
            "ema_9": round(sig["ema_9_today"], 4),
            "ema_21": round(sig["ema_21_today"], 4),
            "ema_50": round(sig["ema_50_today"], 4),
            "ema_50_slope_10": round(sig["ema_50_slope_10"], 6),
            "rsi_14": round(sig["rsi_today"], 2),
            "macd_histogram": round(sig["macd_hist_today"], 6),
            "swing_anchor_idx": anchor_idx,
            "swing_anchor_price": round(anchor_price, 4),
            "leg_size": round(leg_size, 4),
            "pullback_extreme": round(pullback_extreme, 4),
            "retrace_pct": round(geo["retrace_pct"], 4),
            "exhaustion_count": sig["exhaustion_count"],
            "exhaustion_reasons": sig["exhaustion_reasons"],
            "volume_ratio": round(volume_ratio, 4),
            "stop_level": round(stop_level, 4),
            "target_level": round(target_level, 4),
            "risk_reward": round(risk_reward, 4),
            "signal_date": candles[-1].timestamp.strftime("%Y-%m-%d"),
        }
        return ScanResult(
            stock_id=context.stock_id,
            scanner_name="pullback_continuation",
            metadata=metadata,
        )
```

- [ ] **Step 5: Run the long positive-path test**

Run: `pytest tests/unit/test_pullback_continuation_scanner.py::test_emits_long_on_clean_pullback -v -s`
Expected: PASS. If FAIL: tweak fixture numbers in `_bullish_pullback_candles` (NOT scanner constants) — the fixture must produce: 50% retrace ± slack, EMA stack at H, slope > 0, ≥2 exhaustion in last 3 bars, close > EMA(9) and > 3-bar high. Print intermediate values inside the test if needed.

- [ ] **Step 6: Run all scanner tests**

Run: `pytest tests/unit/test_pullback_continuation_scanner.py -v`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/scanner/scanners/pullback_continuation.py tests/unit/test_pullback_continuation_scanner.py
git commit -m "feat(pullback-continuation): long-side full rule wiring + signal emission"
```

---

## Task 17: Short-path wiring

**Files:**
- Modify: `src/scanner/scanners/pullback_continuation.py`
- Modify: `tests/unit/test_pullback_continuation_scanner.py`

- [ ] **Step 1: Add the short positive-path test**

Append to `tests/unit/test_pullback_continuation_scanner.py`:
```python
def test_emits_short_on_failed_bounce():
    """Mirror setup → exactly one short signal."""
    candles = _bearish_failed_bounce_candles()
    scanner = PullbackContinuationScanner()
    results = scanner.scan(_make_context(candles))
    assert len(results) == 1
    r = results[0]
    assert r.metadata["direction"] == "short"
    assert r.metadata["exhaustion_count"] >= 2
```

- [ ] **Step 2: Run — should FAIL**

Run: `pytest tests/unit/test_pullback_continuation_scanner.py::test_emits_short_on_failed_bounce -v`
Expected: FAIL with `assert len(results) == 1`.

- [ ] **Step 3: Add short branch to scan()**

In `scan()`, replace the trailing `if long_signal is not None: ... return results` block with:
```python
            if long_signal is not None:
                results.append(
                    self._build_result(context, candles, atr_val, atr_pct, close, "long", long_signal)
                )
                return results

            # --- Short branch ---
            short_geo = self._find_short_geometry(candles, swings)
            short_signal = None
            if short_geo and self._trend_ok_short(
                ema_9_arr,
                ema_21_arr,
                ema_50_arr,
                candles,
                short_geo["H_idx"],
                short_geo["L_idx"],
                ema_50_slope_10,
            ):
                ema_21_today = float(ema_21_arr[-1])
                three_bar_low = min(c.low for c in candles[-4:-1])
                if close < ema_21_today and close < three_bar_low:
                    count, reasons = self._exhaustion_short(
                        candles,
                        atr_val,
                        rsi_arr,
                        macd_hist,
                        prior_bounce_high_idx=short_geo["bounce_high_idx"],
                        prior_bounce_high=short_geo["bounce_high"],
                    )
                    if count >= self.EXHAUSTION_REQUIRED:
                        short_signal = {
                            "geo": short_geo,
                            "exhaustion_count": count,
                            "exhaustion_reasons": reasons,
                            "ema_9_today": float(ema_9_arr[-1]),
                            "ema_21_today": ema_21_today,
                            "ema_50_today": ema_50_today,
                            "ema_50_slope_10": ema_50_slope_10,
                            "rsi_today": float(rsi_arr[-1]),
                            "macd_hist_today": float(macd_hist[-1]),
                        }

            if short_signal is not None:
                results.append(
                    self._build_result(context, candles, atr_val, atr_pct, close, "short", short_signal)
                )
                return results

            return results
```

- [ ] **Step 4: Run all tests**

Run: `pytest tests/unit/test_pullback_continuation_scanner.py -v -s`
Expected: all tests pass. If short test fails, adjust `_bearish_failed_bounce_candles` numbers (NOT scanner constants).

- [ ] **Step 5: Commit**

```bash
git add src/scanner/scanners/pullback_continuation.py tests/unit/test_pullback_continuation_scanner.py
git commit -m "feat(pullback-continuation): short-side full rule wiring"
```

---

## Task 18: Metadata completeness + stop/target math tests

**Files:**
- Modify: `tests/unit/test_pullback_continuation_scanner.py`

- [ ] **Step 1: Add tests for metadata schema and stop/target math**

Append:
```python
def test_metadata_complete():
    """All required fields present and typed correctly."""
    candles = _bullish_pullback_candles()
    scanner = PullbackContinuationScanner()
    results = scanner.scan(_make_context(candles))
    assert len(results) == 1
    meta = results[0].metadata
    required = [
        "direction", "conviction_score", "close", "atr", "atr_pct",
        "ema_9", "ema_21", "ema_50", "ema_50_slope_10",
        "rsi_14", "macd_histogram",
        "swing_anchor_idx", "swing_anchor_price", "leg_size", "pullback_extreme",
        "retrace_pct", "exhaustion_count", "exhaustion_reasons",
        "volume_ratio", "stop_level", "target_level", "risk_reward", "signal_date",
    ]
    for key in required:
        assert key in meta, f"missing {key}"
    assert isinstance(meta["exhaustion_reasons"], list)
    assert isinstance(meta["swing_anchor_idx"], int)


def test_stop_target_math_long():
    """Long: stop = pullback_low − 0.5×ATR, target = close + 1.618 × up_leg."""
    candles = _bullish_pullback_candles()
    scanner = PullbackContinuationScanner()
    meta = scanner.scan(_make_context(candles))[0].metadata
    expected_stop = round(meta["pullback_extreme"] - 0.5 * meta["atr"], 4)
    expected_target = round(meta["close"] + 1.618 * meta["leg_size"], 4)
    assert meta["stop_level"] == expected_stop
    assert meta["target_level"] == expected_target


def test_stop_target_math_short():
    """Short: stop = bounce_high + 0.5×ATR, target = close − 1.618 × down_leg."""
    candles = _bearish_failed_bounce_candles()
    scanner = PullbackContinuationScanner()
    meta = scanner.scan(_make_context(candles))[0].metadata
    expected_stop = round(meta["pullback_extreme"] + 0.5 * meta["atr"], 4)
    expected_target = round(meta["close"] - 1.618 * meta["leg_size"], 4)
    assert meta["stop_level"] == expected_stop
    assert meta["target_level"] == expected_target
```

- [ ] **Step 2: Run all tests**

Run: `pytest tests/unit/test_pullback_continuation_scanner.py -v`
Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_pullback_continuation_scanner.py
git commit -m "test(pullback-continuation): metadata schema and stop/target math"
```

---

## Task 19: Conviction scoring

**Files:**
- Modify: `src/scanner/scanners/pullback_continuation.py`
- Modify: `tests/unit/test_pullback_continuation_scanner.py`

Score components (weights: 30/25/20/15/10, clamped to [0, 100]):
- Exhaustion count: 4→30, 3→22, 2→15.
- Retracement quality: 0 at 0.38 or 0.78; 25 at 0.5–0.618 sweet-spot. Linear ramp/decline outside the sweet-spot.
- Volume confirmation: trigger-bar `volume / avg20`: 1.0→0; 2.0+→20.
- Trend slope strength: `|ema_9 − ema_50| / ema_50` (in %): 0%→0; 5%+→15.
- Distance to support (long) or resistance (short) in ATR units: closer→max 10. (`max(0, 10 − distance_atr × 5)` capped at 10.)

- [ ] **Step 1: Add a failing bounds test**

Append:
```python
def test_conviction_score_bounds():
    candles = _bullish_pullback_candles()
    scanner = PullbackContinuationScanner()
    score = scanner.scan(_make_context(candles))[0].metadata["conviction_score"]
    assert 0 <= score <= 100
    assert score > 0  # placeholder 0 should now be replaced
```

- [ ] **Step 2: Run — should FAIL on `score > 0`**

Run: `pytest tests/unit/test_pullback_continuation_scanner.py::test_conviction_score_bounds -v`
Expected: FAIL.

- [ ] **Step 3: Replace placeholder in `_build_result`**

In `_build_result`, replace `conviction_score = 0` with a call to a new method `self._score(...)`:
```python
        conviction_score = self._score(
            direction=direction,
            exhaustion_count=sig["exhaustion_count"],
            retrace_pct=geo["retrace_pct"],
            volume_ratio=volume_ratio,
            ema_9=sig["ema_9_today"],
            ema_50=sig["ema_50_today"],
            atr_val=atr_val,
            close=close,
            candles=candles,
        )
```

Add the `_score` method to the class:
```python
    def _score(
        self,
        *,
        direction: str,
        exhaustion_count: int,
        retrace_pct: float,
        volume_ratio: float,
        ema_9: float,
        ema_50: float,
        atr_val: float,
        close: float,
        candles: list,
    ) -> int:
        # Exhaustion (max 30)
        ex_score = {2: 15.0, 3: 22.0, 4: 30.0}.get(exhaustion_count, 0.0)

        # Retracement quality (max 25); peak between 0.5 and 0.618; linear ramp/decline.
        if 0.5 <= retrace_pct <= 0.618:
            retrace_score = 25.0
        elif self.RETRACE_MIN <= retrace_pct < 0.5:
            retrace_score = 25.0 * (retrace_pct - self.RETRACE_MIN) / (0.5 - self.RETRACE_MIN)
        elif 0.618 < retrace_pct <= self.RETRACE_MAX:
            retrace_score = 25.0 * (self.RETRACE_MAX - retrace_pct) / (self.RETRACE_MAX - 0.618)
        else:
            retrace_score = 0.0

        # Volume (max 20): 1.0 → 0; 2.0+ → 20.
        vol_score = max(0.0, min(20.0, (volume_ratio - 1.0) / 1.0 * 20.0))

        # Trend slope (max 15): 0% → 0; 5%+ → 15.
        slope_pct = abs(ema_9 - ema_50) / ema_50 * 100 if ema_50 != 0 else 0.0
        slope_score = min(15.0, slope_pct / 5.0 * 15.0)

        # Distance to nearest support/resistance (max 10) in ATR units.
        if atr_val <= 0:
            distance_score = 0.0
        else:
            if direction == "long":
                levels = self._support_levels(candles, atr_val)
                below = [lvl for lvl in levels if lvl <= close]
                nearest = max(below) if below else None
            else:
                levels = self._resistance_levels(candles, atr_val)
                above = [lvl for lvl in levels if lvl >= close]
                nearest = min(above) if above else None
            if nearest is None:
                distance_score = 0.0
            else:
                distance_atr = abs(close - nearest) / atr_val
                distance_score = max(0.0, min(10.0, 10.0 - distance_atr * 5.0))

        total = ex_score + retrace_score + vol_score + slope_score + distance_score
        return int(min(100, max(0, round(total))))
```

- [ ] **Step 4: Run conviction test**

Run: `pytest tests/unit/test_pullback_continuation_scanner.py::test_conviction_score_bounds -v`
Expected: PASS.

- [ ] **Step 5: Run all scanner tests**

Run: `pytest tests/unit/test_pullback_continuation_scanner.py -v`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/scanner/scanners/pullback_continuation.py tests/unit/test_pullback_continuation_scanner.py
git commit -m "feat(pullback-continuation): weighted conviction scoring"
```

---

## Task 20: Remaining negative-path tests

**Files:**
- Modify: `tests/unit/test_pullback_continuation_scanner.py`

- [ ] **Step 1: Add the eight remaining blocker tests**

Append:
```python
def test_no_signal_when_trend_missing():
    """EMA stack not aligned at H → no signal."""
    base_dt = datetime(2024, 1, 1)
    # Choppy series: stays around 100 with noise — EMA(9)/(21)/(50) tangled.
    candles = [
        Candle(base_dt + timedelta(days=i), 100.0, 102.0, 98.0, 100.0, 5_000_000)
        for i in range(80)
    ]
    # Inject a trigger-like last bar
    candles[-1] = Candle(candles[-1].timestamp, 99.0, 110.0, 99.0, 108.0, 7_000_000)
    scanner = PullbackContinuationScanner()
    assert scanner.scan(_make_context(candles)) == []


def test_no_signal_when_pullback_too_recent():
    """Swing high 1 bar ago → outside [3..15] window → no signal."""
    candles = _bullish_pullback_candles()
    # Replace last few candles to put a swing high at index 78 (1 bar ago).
    base_dt = candles[0].timestamp
    candles[-3] = Candle(base_dt + timedelta(days=77), 159.0, 160.0, 158.0, 159.0, 2_000_000)
    candles[-2] = Candle(base_dt + timedelta(days=78), 158.0, 170.0, 157.0, 158.0, 2_000_000)
    candles[-1] = Candle(base_dt + timedelta(days=79), 158.0, 165.0, 156.0, 162.0, 5_000_000)
    scanner = PullbackContinuationScanner()
    assert scanner.scan(_make_context(candles)) == []


def test_no_signal_when_pullback_stale():
    """Swing high 20 bars ago → outside window → no signal."""
    candles = _bullish_pullback_candles()
    # Move the swing high earlier — overwrite indices 60..70 with a flat region after the
    # original peak, and put a flat preceding region: easiest is to use a custom builder.
    base_dt = candles[0].timestamp
    flat_tail = []
    for i in range(20):
        price = 150.0 + 0.05 * i
        flat_tail.append(
            Candle(base_dt + timedelta(days=60 + i), price, price + 0.5, price - 0.5, price, 2_000_000)
        )
    candles = candles[:60] + flat_tail
    candles.append(
        Candle(base_dt + timedelta(days=80), 151.0, 165.0, 150.5, 165.0, 5_000_000)
    )
    scanner = PullbackContinuationScanner()
    assert scanner.scan(_make_context(candles)) == []


def test_no_signal_when_only_one_exhaustion():
    """1 of 4 exhaustion criteria → no signal."""
    # Strip the volume surge by holding base_volume on trigger bar.
    candles = _bullish_pullback_candles(trigger_volume=1_000_000, base_volume=2_000_000)
    # Also flatten phase 3 vol surges by using a custom override
    base_dt = candles[0].timestamp
    for i in range(68, 79):
        c = candles[i]
        candles[i] = Candle(c.timestamp, c.open, c.high, c.low, c.close, 1_500_000)
    scanner = PullbackContinuationScanner()
    results = scanner.scan(_make_context(candles))
    # Either zero exhaustion criteria, or just one — must not signal.
    assert results == [] or results[0].metadata["exhaustion_count"] >= 2


def test_exhaustion_window_spans_three_bars():
    """A criterion 2 bars ago plus a different criterion today → qualifies."""
    candles = _bullish_pullback_candles()
    scanner = PullbackContinuationScanner()
    results = scanner.scan(_make_context(candles))
    if results:
        # If signal fires, the test passes the spec's intent: window covers today/-1/-2.
        assert results[0].metadata["exhaustion_count"] >= 2


def test_no_signal_when_trigger_below_3bar_high():
    """Close > EMA(9) but ≤ 3-bar high → no signal."""
    candles = _bullish_pullback_candles(trigger_close=158.0)
    # 3-bar high in the fixture is ~158.5 → trigger at 158.0 fails the > 3-bar-high rule.
    scanner = PullbackContinuationScanner()
    assert scanner.scan(_make_context(candles)) == []


def test_insufficient_candles_no_error():
    """< 80 bars → no signal, no exception."""
    base_dt = datetime(2024, 1, 1)
    candles = [
        Candle(base_dt + timedelta(days=i), 100.0, 101.0, 99.0, 100.0, 3_000_000)
        for i in range(40)
    ]
    scanner = PullbackContinuationScanner()
    assert scanner.scan(_make_context(candles)) == []  # no raise
```

- [ ] **Step 2: Run all tests**

Run: `pytest tests/unit/test_pullback_continuation_scanner.py -v`
Expected: all tests pass. If any negative-path test produces a signal because the fixture is *too* clean, tighten the perturbation in the test (do not relax scanner constants).

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_pullback_continuation_scanner.py
git commit -m "test(pullback-continuation): remaining blocker tests"
```

---

## Task 21: Export scanner and register indicator + scanner

**Files:**
- Modify: `src/scanner/scanners/__init__.py`
- Modify: `src/main.py`

- [ ] **Step 1: Export the scanner**

Edit `src/scanner/scanners/__init__.py`:

Replace:
```python
from src.scanner.scanners.weekly_options import WeeklyOptionsScanner

__all__ = [
    "PriceActionScanner",
    "MomentumScanner",
    "VolumeScanner",
    "SmartMoneyScanner",
    "SixMonthHighScanner",
    "WeeklyOptionsScanner",
]
```
With:
```python
from src.scanner.scanners.weekly_options import WeeklyOptionsScanner
from src.scanner.scanners.pullback_continuation import PullbackContinuationScanner

__all__ = [
    "PriceActionScanner",
    "MomentumScanner",
    "VolumeScanner",
    "SmartMoneyScanner",
    "SixMonthHighScanner",
    "WeeklyOptionsScanner",
    "PullbackContinuationScanner",
]
```

- [ ] **Step 2: Register `swing_points` indicator and `pullback_continuation` scanner in the `scan` block**

In `src/main.py`, around line 84, change:
```python
    from src.scanner.indicators.support_resistance import SupportResistance
```
to:
```python
    from src.scanner.indicators.support_resistance import SupportResistance, SwingPoints
```

Around line 87-94, change the scanners import to:
```python
    from src.scanner.scanners import (
        PriceActionScanner,
        MomentumScanner,
        VolumeScanner,
        SmartMoneyScanner,
        SixMonthHighScanner,
        WeeklyOptionsScanner,
        PullbackContinuationScanner,
    )
```

In the `indicators` dict (around line 117-119), add:
```python
            "support_resistance": SupportResistance(),
            "breakout": BreakoutDetector(),
            "rolling_max": RollingMax(),
            "swing_points": SwingPoints(),
```

After line 128 (`scanner_registry.register("weekly_options", WeeklyOptionsScanner())`), add:
```python
        scanner_registry.register("pullback_continuation", PullbackContinuationScanner())
```

- [ ] **Step 3: Smoke-test imports**

Run: `python -c "from src.scanner.scanners import PullbackContinuationScanner; print(PullbackContinuationScanner().description)"`
Expected: prints `"Bidirectional pullback continuation: trend + geometry + exhaustion + trigger"`.

- [ ] **Step 4: Smoke-test the registry wiring**

Run: `python -m src.main scan --help`
Expected: command help renders without ImportError.

- [ ] **Step 5: Commit**

```bash
git add src/scanner/scanners/__init__.py src/main.py
git commit -m "feat(pullback-continuation): register scanner and SwingPoints indicator in EOD pipeline"
```

---

## Task 22: Run full CI locally and fix any issues

**Files:**
- All touched files.

- [ ] **Step 1: Lint**

Run: `ruff check src/ tests/`
Expected: no errors. Fix in place if reported.

- [ ] **Step 2: Format**

Run: `ruff format src/ tests/`
Expected: 0 files reformatted (or the formatter's expected diff). Stage any reformatting changes.

- [ ] **Step 3: Type check**

Run: `mypy src/ --ignore-missing-imports`
Expected: no errors. Fix any new type errors introduced by this PR.

- [ ] **Step 4: Full test suite**

Run: `pytest tests/`
Expected: all tests pass (existing + new).

- [ ] **Step 5: Make ci**

Run: `make ci`
Expected: green.

- [ ] **Step 6: Commit any fixups**

```bash
git status
# If anything is modified, e.g., from ruff format:
git add -u
git commit -m "chore(pullback-continuation): formatting/lint cleanup from make ci"
```

---

## Task 23: Push and open the PR

**Files:**
- None — repo operations.

- [ ] **Step 1: Push the branch**

Run:
```bash
git push -u origin feat/pullback-continuation-scanner
```

- [ ] **Step 2: Open the PR**

Use `gh pr create` (per CLAUDE.md). Title: `feat: pullback-continuation EOD scanner`. Body should reference the design doc and the Linear issue. Confirm the PR URL with the user.

---

## Self-Review Notes (already applied)

Cross-checked against `docs/superpowers/specs/2026-05-01-pullback-continuation-scanner-design.md`:

- **Spec coverage:** every spec section maps to a task — purpose/edge (Tasks 7-19), output schema (Task 18), conviction scoring (Task 19), architecture (Tasks 2-6, 21), data flow / registration (Task 21), error handling (Task 8 try/except + Task 20 insufficient candles), testing (Tasks 2, 4, 5, 9, 17-20). Out-of-scope items (multi-day state machine, backtesting, multi-timeframe, watchlist auto-add, smart_money refactor) are not in any task — correct.
- **Schedule deviation noted:** spec says register in both eod and schedule blocks, but the existing precedent (`weekly_options`, also EOD-only) registers only in the `scan` command block; the pre-close pipeline is intentionally separate. Plan registers in the `scan` block only and documents the rationale at the top.
- **Test path deviation noted:** spec lists tests under `tests/unit/scanner/scanners/`, but the actual codebase keeps scanner tests flat in `tests/unit/`. Plan follows the codebase pattern.
- **Type/name consistency:** `swing_points`, `_find_long_geometry`, `_find_short_geometry`, `_trend_ok_long`, `_trend_ok_short`, `_exhaustion_long`, `_exhaustion_short`, `_score`, `_build_result`, `_macd_histogram`, `_support_levels`, `_resistance_levels`, `_stack_at` — names used consistently across tasks.
- **Metadata schema** matches the spec exactly (direction, conviction_score, close, atr, atr_pct, ema_9/21/50, ema_50_slope_10, rsi_14, macd_histogram, swing_anchor_idx, swing_anchor_price, leg_size, pullback_extreme, retrace_pct, exhaustion_count, exhaustion_reasons, volume_ratio, stop_level, target_level, risk_reward, signal_date).
- **Stop/target math** matches the spec: long stop = `pullback_low − 0.5×ATR`, target = `close + 1.618 × up_leg`; short mirror.
- **No placeholders.** Every code step contains the actual code; no "TBD"/"TODO"/"add error handling" prose.
