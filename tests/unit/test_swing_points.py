"""Unit tests for SwingPoints indicator."""

from datetime import datetime, timedelta
from typing import List


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
    highs = [10.0, 11.0, 12.0, 20.0, 12.0, 11.0, 10.0, 9.0, 8.0]
    lows = [h - 5.0 for h in highs]
    sp = SwingPoints()
    result = sp.compute(_candles(highs, lows), lookback=60)
    assert (3, 20.0) in [(int(i), float(p)) for i, p in result["highs"]]


def test_swing_points_basic_low():
    """Bar i is a swing low if low[i] < min(low[i-2..i-1]) AND low[i] < min(low[i+1..i+2])."""
    highs = [20.0, 19.0, 18.0, 10.0, 18.0, 19.0, 20.0, 21.0, 22.0]
    lows = [h - 5.0 for h in highs]
    sp = SwingPoints()
    result = sp.compute(_candles(highs, lows), lookback=60)
    assert (3, lows[3]) in [(int(i), float(p)) for i, p in result["lows"]]


def test_swing_points_excludes_edges():
    """Peaks within 2 bars of array start/end must be excluded (need 2 bars on each side)."""
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
