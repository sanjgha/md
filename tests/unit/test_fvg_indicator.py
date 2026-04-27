"""Unit tests for FVG detection indicator."""

from src.scanner.indicators.patterns.fvg import FVGDetector
from src.data_provider.base import Candle
from datetime import datetime, timedelta


def create_candle(open_price, high, low, close, volume, days_ago):
    """Helper to create test candles."""
    ts = datetime.utcnow() - timedelta(days=days_ago)
    return Candle(timestamp=ts, open=open_price, high=high, low=low, close=close, volume=volume)


def test_bullish_fvg_detection():
    """Detect bullish FVG when candle[i].high < candle[i+2].low"""
    detector = FVGDetector()

    # Create candles with bullish gap: candle 0 high < candle 2 low
    candles = [
        create_candle(100, 102, 99, 101, 1000, 10),  # i=0: high=102
        create_candle(101, 103, 100, 102, 1100, 9),  # i=1: middle candle
        create_candle(102, 105, 103, 104, 1200, 8),  # i=2: low=103 > 102 (gap!)
        create_candle(104, 106, 103, 105, 1300, 7),  # i=3: after gap
        create_candle(105, 107, 104, 106, 1400, 6),  # i=4: after gap
    ]

    fvgs = detector.detect_fvgs(candles)

    assert len(fvgs) == 1
    assert fvgs[0].bullish is True
    assert fvgs[0].top == 103.0  # candle[2].low
    assert fvgs[0].bottom == 102.0  # candle[0].high
    assert fvgs[0].candle_index == 0


def test_bearish_fvg_detection():
    """Detect bearish FVG when candle[i].low > candle[i+2].high"""
    detector = FVGDetector()

    # Create candles with bearish gap: candle 0 low > candle 2 high
    candles = [
        create_candle(105, 107, 104, 106, 1000, 10),  # i=0: low=104
        create_candle(103, 105, 102, 104, 1100, 9),  # i=1: middle candle
        create_candle(100, 102, 99, 101, 1200, 8),  # i=2: high=102 < 104 (gap!)
        create_candle(101, 103, 100, 102, 1300, 7),  # i=3: after gap
        create_candle(100, 102, 99, 101, 1400, 6),  # i=4: after gap
    ]

    fvgs = detector.detect_fvgs(candles)

    assert len(fvgs) == 1
    assert fvgs[0].bullish is False
    assert fvgs[0].top == 104.0  # candle[0].low
    assert fvgs[0].bottom == 102.0  # candle[2].high
    assert fvgs[0].candle_index == 0


def test_fvg_below_threshold_filtered():
    """FVGs below 0.75% threshold should be filtered out."""
    detector = FVGDetector()

    # Create candles with tiny gap (0.1%)
    candles = [
        create_candle(100.0, 100.5, 99.5, 100.0, 1000, 10),  # i=0: high=100.5
        create_candle(100.0, 101.0, 99.5, 100.5, 1100, 9),  # i=1
        create_candle(100.5, 101.0, 100.6, 100.8, 1200, 8),  # i=2: low=100.6 (0.1% gap)
    ]

    fvgs = detector.detect_fvgs(candles)

    # Gap is 100.6 - 100.5 = 0.1, which is 0.1% of 100.5 (< 0.75%)
    assert len(fvgs) == 0
