"""Tests for FractalSwings indicator."""

from src.scanner.indicators.patterns.fvg import FractalSwings
from src.data_provider.base import Candle
from datetime import datetime, timedelta


def create_candle(open_price, high, low, close, volume, days_ago):
    """Helper to create a candle with timestamp."""
    ts = datetime.utcnow() - timedelta(days=days_ago)
    return Candle(timestamp=ts, open=open_price, high=high, low=low, close=close, volume=volume)


def test_swing_high_detection():
    """Detect 5-bar fractal swing high: 2 lower candles on each side."""
    detector = FractalSwings()

    # Create swing high at index 5
    candles = [
        create_candle(100, 102, 98, 101, 1000, 10),  # i=0
        create_candle(101, 103, 99, 102, 1100, 9),  # i=1
        create_candle(102, 104, 100, 103, 1200, 8),  # i=2
        create_candle(103, 105, 101, 104, 1300, 7),  # i=3
        create_candle(104, 108, 102, 106, 1400, 6),  # i=4
        create_candle(106, 110, 105, 108, 1500, 5),  # i=5: SWING HIGH (110)
        create_candle(108, 109, 106, 107, 1600, 4),  # i=6
        create_candle(107, 108, 105, 106, 1700, 3),  # i=7
    ]

    swings = detector.detect_swings(candles)

    swing_highs = [s for s in swings if s.is_high]

    assert len(swing_highs) == 1
    assert swing_highs[0].price == 110.0
    assert swing_highs[0].is_high is True
    assert swing_highs[0].candle_index == 5


def test_swing_low_detection():
    """Detect 5-bar fractal swing low: 2 higher candles on each side."""
    detector = FractalSwings()

    # Create swing low at index 4
    candles = [
        create_candle(100, 105, 95, 100, 1000, 10),  # i=0
        create_candle(100, 104, 96, 100, 1100, 9),  # i=1
        create_candle(100, 103, 98, 100, 1200, 8),  # i=2
        create_candle(100, 102, 99, 100, 1300, 7),  # i=3
        create_candle(100, 101, 90, 95, 1400, 6),  # i=4: SWING LOW (90)
        create_candle(95, 102, 94, 100, 1500, 5),  # i=5
        create_candle(100, 103, 96, 100, 1600, 4),  # i=6
    ]

    swings = detector.detect_swings(candles)

    swing_lows = [s for s in swings if not s.is_high]

    assert len(swing_lows) == 1
    assert swing_lows[0].price == 90.0
    assert swing_lows[0].is_high is False
    assert swing_lows[0].candle_index == 4


def test_insufficient_candles():
    """Return empty list when fewer than 5 candles."""
    detector = FractalSwings()

    candles = [
        create_candle(100, 102, 98, 101, 1000, 4),
        create_candle(101, 103, 99, 102, 1100, 3),
    ]

    swings = detector.detect_swings(candles)

    assert len(swings) == 0


def test_multiple_swings():
    """Detect multiple swing highs and lows in sequence."""
    detector = FractalSwings()

    # Create pattern with swing high at i=4 and swing low at i=9
    candles = [
        create_candle(100, 102, 98, 101, 1000, 15),  # i=0
        create_candle(101, 103, 99, 102, 1100, 14),  # i=1
        create_candle(102, 105, 100, 103, 1200, 13),  # i=2
        create_candle(103, 107, 101, 104, 1300, 12),  # i=3
        create_candle(104, 110, 102, 106, 1400, 11),  # i=4: SWING HIGH (110)
        create_candle(106, 109, 104, 107, 1500, 10),  # i=5
        create_candle(107, 108, 103, 105, 1600, 9),  # i=6
        create_candle(105, 106, 102, 104, 1700, 8),  # i=7
        create_candle(104, 105, 98, 103, 1800, 7),  # i=8
        create_candle(103, 104, 95, 100, 1900, 6),  # i=9: SWING LOW (95)
        create_candle(100, 102, 96, 101, 2000, 5),  # i=10
        create_candle(101, 103, 97, 102, 2100, 4),  # i=11
    ]

    swings = detector.detect_swings(candles)

    assert len(swings) == 2

    swing_highs = [s for s in swings if s.is_high]
    swing_lows = [s for s in swings if not s.is_high]

    assert len(swing_highs) == 1
    assert swing_highs[0].price == 110.0
    assert swing_highs[0].candle_index == 4

    assert len(swing_lows) == 1
    assert swing_lows[0].price == 95.0
    assert swing_lows[0].candle_index == 9
