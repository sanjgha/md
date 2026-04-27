"""Tests for RollingMax indicator."""

import numpy as np
from src.scanner.indicators.rolling_max import RollingMax
from src.data_provider.base import Candle
from datetime import datetime, timedelta


def make_candles(closes):
    """Create candles from close prices."""
    base = datetime(2024, 1, 1)
    return [
        Candle(base + timedelta(days=i), c, c + 1, c - 1, c, 1000) for i, c in enumerate(closes)
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
