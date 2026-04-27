# Six-Month High Scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a scanner that detects stocks whose daily close price reached a 6-month high within the past 5 trading days, using a reusable rolling_max indicator.

**Architecture:**
- New `RollingMax` indicator computes the highest close price over N periods
- `SixMonthHighScanner` uses this indicator to find stocks that broke their 6-month high in the last 5 trading days
- Follows existing Scanner pattern: inherits from `Scanner`, uses `ScanContext`, returns `List[ScanResult]`

**Tech Stack:**
- NumPy for array operations
- SQLAlchemy ORM (DailyCandle model)
- pytest for testing
- Follows existing codebase patterns (SMA, RSI indicators; PriceActionScanner, MomentumScanner)

---

## Task 1: Create RollingMax Indicator

**Files:**
- Create: `src/scanner/indicators/rolling_max.py`

- [ ] **Step 1: Write the failing test for RollingMax indicator**

Create file: `tests/unit/test_rolling_max_indicator.py`

```python
"""Tests for RollingMax indicator."""
import numpy as np
from src.scanner.indicators.rolling_max import RollingMax
from src.data_provider.base import Candle
from datetime import datetime, timedelta


def make_candles(closes):
    """Create candles from close prices."""
    base = datetime(2024, 1, 1)
    return [
        Candle(base + timedelta(days=i), c, c+1, c-1, c, 1000)
        for i, c in enumerate(closes)
    ]


def test_rolling_max_returns_array():
    """RollingMax should return numpy array."""
    indicator = RollingMax()
    candles = make_candles([100, 101, 102, 103, 104])
    result = indicator.compute(candles, period=3)
    assert isinstance(result, np.ndarray)


def test_rolling_max_period_3():
    """RollingMax with period=3 should return max of each 3-candle window."""
    indicator = RollingMax()
    candles = make_candles([100, 105, 102, 108, 103])
    result = indicator.compute(candles, period=3)

    # Windows: [100,105,102]→105, [105,102,108]→108, [102,108,103]→108
    expected = np.array([105.0, 108.0, 108.0])
    np.testing.assert_array_equal(result, expected)


def test_rolling_max_insufficient_data():
    """RollingMax should return empty array when not enough candles."""
    indicator = RollingMax()
    candles = make_candles([100, 101])
    result = indicator.compute(candles, period=5)
    assert len(result) == 0


def test_rolling_max_period_126():
    """RollingMax with period=126 (6 months of trading days)."""
    indicator = RollingMax()
    closes = [100.0 + i for i in range(150)]
    candles = make_candles(closes)
    result = indicator.compute(candles, period=126)

    # Should have 150 - 126 + 1 = 25 values
    assert len(result) == 25
    # First window [100..225] max = 225
    assert result[0] == 225.0
    # Last window [124..249] max = 249
    assert result[-1] == 249.0


def test_rolling_max_all_same():
    """RollingMax should handle all identical values."""
    indicator = RollingMax()
    candles = make_candles([100.0] * 20)
    result = indicator.compute(candles, period=5)
    expected = np.array([100.0] * 16)
    np.testing.assert_array_equal(result, expected)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_rolling_max_indicator.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'src.scanner.indicators.rolling_max'"

- [ ] **Step 3: Write minimal RollingMax implementation**

Create file: `src/scanner/indicators/rolling_max.py`

```python
"""Rolling maximum indicator for detecting price highs over N periods."""

import numpy as np
from typing import List
from src.data_provider.base import Candle
from src.scanner.indicators.base import Indicator


class RollingMax(Indicator):
    """Rolling maximum of close prices over N periods."""

    def compute(self, candles: List[Candle], period: int = 126, **kwargs) -> np.ndarray:
        """Compute rolling maximum of closing prices.

        Args:
            candles: List of Candle objects
            period: Number of periods for rolling window (default 126 for ~6 months)

        Returns:
            numpy array where each value is the max close in the window.
            Length is len(candles) - period + 1.
            Returns empty array if len(candles) < period.
        """
        closes = np.array([c.close for c in candles], dtype=float)

        if len(closes) < period:
            return np.array([])

        # Use pandas-like rolling max: for each window of size `period`, take max
        # Result has length: len(closes) - period + 1
        result = np.zeros(len(closes) - period + 1)

        for i in range(len(result)):
            window = closes[i : i + period]
            result[i] = np.max(window)

        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_rolling_max_indicator.py -v`

Expected: All tests PASS

- [ ] **Step 5: Register indicator in __init__.py**

Add to file: `src/scanner/indicators/__init__.py`

```python
"""Technical indicators package."""

from src.scanner.indicators.base import Indicator
from src.scanner.indicators.cache import IndicatorCache
from src.scanner.indicators.rolling_max import RollingMax

__all__ = ["Indicator", "IndicatorCache", "RollingMax"]
```

- [ ] **Step 6: Commit**

```bash
git add src/scanner/indicators/rolling_max.py src/scanner/indicators/__init__.py tests/unit/test_rolling_max_indicator.py
git commit -m "feat: add RollingMax indicator for 6-month high detection

Add RollingMax indicator that computes rolling maximum of close prices
over N periods. Used by SixMonthHighScanner to detect when stocks break
their 6-month high. Returns numpy array of max values for each window.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Create SixMonthHighScanner

**Files:**
- Create: `src/scanner/scanners/six_month_high.py`

- [ ] **Step 1: Write the failing test for SixMonthHighScanner**

Create file: `tests/unit/test_six_month_high_scanner.py`

```python
"""Tests for SixMonthHighScanner."""

from datetime import datetime, timedelta
from src.scanner.scanners.six_month_high import SixMonthHighScanner
from src.scanner.context import ScanContext
from src.scanner.indicators.cache import IndicatorCache
from src.scanner.indicators.rolling_max import RollingMax
from src.data_provider.base import Candle


def make_scan_context(stock_id=1, symbol="AAPL", closes=None):
    """Create a ScanContext with daily candles."""
    if closes is None:
        closes = [100.0] * 131

    base = datetime(2024, 1, 1)
    candles = [
        Candle(base + timedelta(days=i), c, c+1, c-1, c, 1000)
        for i, c in enumerate(closes)
    ]

    indicators = {"rolling_max": RollingMax()}
    return ScanContext(
        stock_id=stock_id,
        symbol=symbol,
        daily_candles=candles,
        intraday_candles={},
        indicator_cache=IndicatorCache(indicators),
    )


def test_six_month_high_scanner_returns_list():
    """Scanner should return a list (possibly empty)."""
    context = make_scan_context()
    scanner = SixMonthHighScanner()
    results = scanner.scan(context)
    assert isinstance(results, list)


def test_six_month_high_insufficient_candles():
    """Scanner should return empty list with fewer than 131 candles."""
    context = make_scan_context(closes=[100.0] * 100)
    scanner = SixMonthHighScanner()
    results = scanner.scan(context)
    assert results == []


def test_six_month_high_no_match():
    """Scanner should return empty when no new 6-month high in last 5 days."""
    # Candles 0-124: Various prices up to 200
    # Candles 125-130: All below 200 (no new high)
    closes = [100.0 + i for i in range(125)]  # Ends at 224
    closes.extend([210.0, 212.0, 215.0, 218.0, 220.0, 222.0])  # All below 224

    context = make_scan_context(closes=closes)
    scanner = SixMonthHighScanner()
    results = scanner.scan(context)
    assert results == []


def test_six_month_high_match_today():
    """Scanner should detect new 6-month high today (index -1)."""
    # Candles 0-124: Various prices, max in first 126 = 200
    # Candle 130 (today): Close at 205, breaking 6-month high
    closes = [150.0 + (i % 50) for i in range(125)]  # Oscillates 150-199
    closes.extend([195.0, 196.0, 197.0, 198.0, 199.0, 205.0])  # Last is new high

    context = make_scan_context(closes=closes)
    scanner = SixMonthHighScanner()
    results = scanner.scan(context)

    assert len(results) == 1
    assert results[0].stock_id == 1
    assert results[0].scanner_name == "six_month_high"
    assert results[0].metadata["current_close"] == 205.0
    assert results[0].metadata["days_ago"] == 0


def test_six_month_high_match_3_days_ago():
    """Scanner should detect new 6-month high 3 days ago."""
    # Build 131 candles where 6-month high is broken 3 days ago
    closes = [150.0 + (i % 50) for i in range(125)]  # Oscillates 150-199
    # Last 6 candles: 3 days ago (index -3) breaks the high
    closes.extend([195.0, 196.0, 205.0, 198.0, 197.0, 196.0])

    context = make_scan_context(closes=closes)
    scanner = SixMonthHighScanner()
    results = scanner.scan(context)

    assert len(results) == 1
    assert results[0].metadata["current_close"] == 205.0
    assert results[0].metadata["days_ago"] == 3


def test_six_month_high_multiple_matches_returns_most_recent():
    """Scanner should return only most recent when multiple new highs."""
    # Multiple new highs in 5-day window
    closes = [150.0 + (i % 50) for i in range(125)]  # Max ~199
    # Last 5: break high at -4 (202), break again at -1 (205) → should return -1
    closes.extend([195.0, 202.0, 200.0, 201.0, 203.0, 205.0])

    context = make_scan_context(closes=closes)
    scanner = SixMonthHighScanner()
    results = scanner.scan(context)

    assert len(results) == 1
    assert results[0].metadata["current_close"] == 205.0
    assert results[0].metadata["days_ago"] == 0


def test_six_month_high_exactly_131_candles():
    """Scanner should work with exactly 131 candles (boundary case)."""
    closes = [150.0 + (i % 50) for i in range(125)]
    closes.extend([195.0, 196.0, 197.0, 198.0, 199.0, 205.0])

    context = make_scan_context(closes=closes)
    scanner = SixMonthHighScanner()
    results = scanner.scan(context)

    assert len(results) == 1


def test_six_month_high_metadata_fields():
    """Scanner should include all required metadata fields."""
    closes = [150.0 + (i % 50) for i in range(125)]
    closes.extend([195.0, 196.0, 205.0, 198.0, 197.0, 196.0])

    context = make_scan_context(closes=closes)
    scanner = SixMonthHighScanner()
    results = scanner.scan(context)

    assert len(results) == 1
    metadata = results[0].metadata
    assert "six_month_high" in metadata
    assert "current_close" in metadata
    assert "days_ago" in metadata
    assert "high_date" in metadata
    assert isinstance(metadata["six_month_high"], float)
    assert isinstance(metadata["current_close"], float)
    assert isinstance(metadata["days_ago"], int)


def test_six_month_high_declining_price():
    """Scanner should return empty for declining price series."""
    closes = [200.0 - i * 0.5 for i in range(131)]  # Steadily declining

    context = make_scan_context(closes=closes)
    scanner = SixMonthHighScanner()
    results = scanner.scan(context)

    assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_six_month_high_scanner.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'src.scanner.scanners.six_month_high'"

- [ ] **Step 3: Write SixMonthHighScanner implementation**

Create file: `src/scanner/scanners/six_month_high.py`

```python
"""Six-month high scanner: detects stocks that hit 6-month high (close) in past 5 trading days."""

import logging
from typing import List
from src.scanner.base import Scanner, ScanResult
from src.scanner.context import ScanContext

logger = logging.getLogger(__name__)


class SixMonthHighScanner(Scanner):
    """Scan for stocks that hit 6-month high (close price) in past 5 trading days."""

    timeframe = "daily"
    description = "Stocks that hit 6-month high (close) in past 5 trading days"

    def scan(self, context: ScanContext) -> List[ScanResult]:
        """Return matches when close price broke 6-month high in last 5 trading days.

        Algorithm:
        1. Need at least 131 candles (126 for reference window + 5 for lookback)
        2. Compute rolling_max with period=126
        3. Get reference high from rolling_max[-6] (6-month high as of 6 days ago)
        4. Check if any of last 5 candles (indices -5 to -1) exceed this reference
        5. Return only the most recent match if multiple found

        Args:
            context: ScanContext with daily_candles and indicator_cache

        Returns:
            List of ScanResult (empty or single result with most recent match)
        """
        matches: List[ScanResult] = []

        # Need at least 131 candles: 126 for 6-month window + 5 for lookback
        if len(context.daily_candles) < 131:
            return matches

        try:
            # Get rolling maximum indicator with 126-period window (~6 trading months)
            rolling_max = context.get_indicator("rolling_max", period=126)

            if len(rolling_max) < 6:
                return matches

            # Reference high: 6-month high as of 6 days ago (before lookback window)
            six_month_high = float(rolling_max[-6])

            # Check last 5 candles for new 6-month highs
            # Indices: -5 (5 days ago), -4, -3, -2, -1 (today)
            most_recent_match_idx = None
            most_recent_match_close = None

            for offset in range(-5, 0):  # -5, -4, -3, -2, -1
                candle = context.daily_candles[offset]
                if candle.close > six_month_high:
                    most_recent_match_idx = offset
                    most_recent_match_close = candle.close

            # If we found a match, create ScanResult for the most recent one
            if most_recent_match_idx is not None:
                # Calculate days_ago: offset -1 = 0 days, offset -2 = 1 day, etc.
                days_ago = abs(most_recent_match_idx + 1)
                match_candle = context.daily_candles[most_recent_match_idx]

                matches.append(
                    ScanResult(
                        stock_id=context.stock_id,
                        scanner_name="six_month_high",
                        metadata={
                            "six_month_high": six_month_high,
                            "current_close": most_recent_match_close,
                            "days_ago": days_ago,
                            "high_date": match_candle.timestamp.strftime("%Y-%m-%d"),
                        },
                    )
                )

        except Exception:
            logger.exception(f"SixMonthHighScanner failed for {context.symbol}")

        return matches
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_six_month_high_scanner.py -v`

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/scanner/scanners/six_month_high.py tests/unit/test_six_month_high_scanner.py
git commit -m "feat: add SixMonthHighScanner for 6-month high detection

Add scanner that detects stocks whose daily close price reached a 6-month
high (126 trading days) within the past 5 trading days. Returns only the
most recent occurrence. Uses RollingMax indicator for efficiency.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Register Scanner in Package

**Files:**
- Modify: `src/scanner/scanners/__init__.py`

- [ ] **Step 1: Add SixMonthHighScanner to scanner package exports**

Edit file: `src/scanner/scanners/__init__.py`

Add this import at the top:
```python
from src.scanner.scanners.six_month_high import SixMonthHighScanner
```

Add `"SixMonthHighScanner"` to the `__all__` list.

The complete file should look like:

```python
"""Scanner implementations: price action, momentum, volume, smart money, and six-month high."""

from src.scanner.scanners.price_action import PriceActionScanner
from src.scanner.scanners.momentum_scan import MomentumScanner
from src.scanner.scanners.volume_scan import VolumeScanner
from src.scanner.scanners.smart_money import SmartMoneyScanner
from src.scanner.scanners.six_month_high import SixMonthHighScanner

__all__ = [
    "PriceActionScanner",
    "MomentumScanner",
    "VolumeScanner",
    "SmartMoneyScanner",
    "SixMonthHighScanner",
]
```

- [ ] **Step 2: Verify exports work**

Run: `python -c "from src.scanner.scanners import SixMonthHighScanner; print(SixMonthHighScanner.description)"`

Expected output: `Stocks that hit 6-month high (close) in past 5 trading days`

- [ ] **Step 3: Commit**

```bash
git add src/scanner/scanners/__init__.py
git commit -m "feat: register SixMonthHighScanner in scanner package

Export SixMonthHighScanner from scanner package __init__.py so it can
be imported and registered with ScannerRegistry.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Run Full Test Suite

**Files:**
- No file creation/modification

- [ ] **Step 1: Run all unit tests**

Run: `pytest tests/unit/ -v --cov=src --cov-report=term-missing`

Expected: All tests pass, coverage shows new files covered

- [ ] **Step 2: Run linter**

Run: `ruff check src/scanner/indicators/rolling_max.py src/scanner/scanners/six_month_high.py`

Expected: No errors

- [ ] **Step 3: Run type checker**

Run: `mypy src/scanner/indicators/rolling_max.py src/scanner/scanners/six_month_high.py --ignore-missing-imports`

Expected: No errors

- [ ] **Step 4: Run formatter check**

Run: `black --check src/scanner/indicators/rolling_max.py src/scanner/scanners/six_month_high.py tests/unit/test_rolling_max_indicator.py tests/unit/test_six_month_high_scanner.py`

Expected: No reformatting needed

- [ ] **Step 5: Run full CI locally**

Run: `make ci`

Expected: All checks pass (lint, type-check, tests)

---

## Task 5: Documentation Update (Optional)

**Files:**
- Modify: `README.md` or `docs/` if scanner documentation exists

- [ ] **Step 1: Check if scanner documentation exists**

Run: `ls -la docs/ | grep -i scanner`

If scanner documentation file exists, add entry for SixMonthHighScanner.

- [ ] **Step 2: Add documentation entry if applicable**

If documentation exists, add:
```markdown
### SixMonthHighScanner

Detects stocks whose daily close price has reached the highest level in the past 126 trading days (approximately 6 months), occurring within the last 5 trading days.

**Parameters:** None

**Output metadata:**
- `six_month_high`: The 6-month high price reference
- `current_close`: The price that broke the high
- `days_ago`: How many days ago the high occurred (0=today)
- `high_date`: Date when the high occurred
```

- [ ] **Step 3: Commit if changes made**

```bash
git add docs/
git commit -m "docs: add SixMonthHighScanner to scanner documentation"
```

---

## Task 6: Integration Verification

**Files:**
- No file creation/modification

- [ ] **Step 1: Verify scanner can be registered in registry**

Create test script (temporarily, don't commit):

```bash
python -c "
from src.scanner.scanners import SixMonthHighScanner
from src.scanner.registry import ScannerRegistry

registry = ScannerRegistry()
scanner = SixMonthHighScanner()
registry.register('six_month_high', scanner)

retrieved = registry.get('six_month_high')
print(f'Registered: {retrieved.description}')
assert retrieved is scanner
print('✓ Scanner registration works')
"
```

Expected output: Registered: Stocks that hit 6-month high (close) in past 5 trading days
                  ✓ Scanner registration works

- [ ] **Step 2: Clean up test script**

Run: `rm -f test_script.py` (if you created a file)

---

## Task 7: Final Verification

**Files:**
- No file creation/modification

- [ ] **Step 1: Verify all tests pass**

Run: `pytest tests/unit/test_rolling_max_indicator.py tests/unit/test_six_month_high_scanner.py -v`

Expected: All 14 tests pass (6 for RollingMax, 8 for SixMonthHighScanner)

- [ ] **Step 2: Check git diff**

Run: `git diff HEAD~3`

Expected: Shows all changes from Tasks 1-3 (indicator, scanner, registration)

- [ ] **Step 3: View commit history**

Run: `git log --oneline -4`

Expected: Shows 3-4 commits related to six-month high feature

- [ ] **Step 4: Final commit message summary**

All commits should follow Conventional Commits format with proper Co-Authored-By footer.

---

## Summary

This plan creates:
- **RollingMax indicator** (`src/scanner/indicators/rolling_max.py`) — reusable for any "N-period high" detection
- **SixMonthHighScanner** (`src/scanner/scanners/six_month_high.py`) — detects 6-month highs in last 5 trading days
- **Comprehensive tests** (14 test cases covering edge cases, multiple matches, metadata)
- Follows TDD: test → implementation → verification → commit
- Each task is 2-5 minutes, self-contained

The scanner returns only the most recent match when a stock breaks its 6-month high multiple times in the lookback window, with clear metadata indicating the high price, current close, days ago, and date.
