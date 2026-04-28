"""Unit tests for BBWidthPercentile indicator."""

import numpy as np
from datetime import datetime, timedelta
from src.scanner.indicators.volatility import BBWidthPercentile
from src.data_provider.base import Candle


def make_candles(closes, volume=1_000_000):
    base = datetime(2024, 1, 1)
    return [
        Candle(base + timedelta(days=i), c, c + 1.0, c - 1.0, c, volume)
        for i, c in enumerate(closes)
    ]


def test_returns_empty_when_insufficient_candles():
    """Need at least period + lookback - 1 candles."""
    indicator = BBWidthPercentile()
    candles = make_candles([100.0] * 78)  # period=20, lookback=60 → need 79
    result = indicator.compute(candles, period=20, lookback=60)
    assert len(result) == 0


def test_output_length():
    """Output length = len(candles) - period - lookback + 2."""
    indicator = BBWidthPercentile()
    candles = make_candles([100.0] * 80)
    result = indicator.compute(candles, period=20, lookback=60)
    assert len(result) == 80 - 20 - 60 + 2  # == 2


def test_constant_series_returns_50():
    """Constant closes → all BB widths equal → midrank percentile = 50."""
    indicator = BBWidthPercentile()
    candles = make_candles([100.0] * 85)
    result = indicator.compute(candles, period=20, lookback=60)
    assert len(result) > 0
    np.testing.assert_array_almost_equal(result, 50.0, decimal=1)


def test_rising_bb_width_approaches_100():
    """Monotonically widening volatility → last value's percentile should be high."""
    indicator = BBWidthPercentile()
    # Phase 1 (60): tight, Phase 2 (25): increasingly volatile with growing amplitude
    closes = [100.0] * 60
    for i in range(25):
        # Increasing oscillation amplitude: 1, 2, 3, ..., 25
        closes.append(100.0 + 4.0 * (1 + i) * (1 if i % 2 == 0 else -1))
    candles = make_candles(closes)
    result = indicator.compute(candles, period=20, lookback=60)
    assert len(result) > 0
    # Last value should be well above 50 (current window is widest)
    assert result[-1] > 60


def test_tight_current_window_gives_low_percentile():
    """Tight recent range after volatile history → low percentile (squeeze)."""
    import math

    indicator = BBWidthPercentile()
    # 60 candles: volatile (±10 oscillation)
    closes = [100.0 + 10.0 * math.sin(i * 0.6) for i in range(60)]
    # 25 candles: very tight (±0.2 oscillation)
    closes += [100.0 + 0.2 * math.sin(i * 1.0) for i in range(25)]
    candles = make_candles(closes)
    result = indicator.compute(candles, period=20, lookback=60)
    assert len(result) > 0
    # Today is in a squeeze — should be well below 25th percentile
    assert result[-1] < 25


def test_values_bounded_0_to_100():
    """All percentile values must stay in [0, 100]."""
    import math

    indicator = BBWidthPercentile()
    closes = [100.0 + 5.0 * math.sin(i * 0.5) for i in range(90)]
    candles = make_candles(closes)
    result = indicator.compute(candles, period=20, lookback=60)
    assert np.all(result >= 0)
    assert np.all(result <= 100)
