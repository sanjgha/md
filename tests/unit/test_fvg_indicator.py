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


def test_fvg_merging_no_overlap():
    """Non-overlapping FVGs should remain separate."""
    detector = FVGDetector()

    # Create two separate bullish FVGs with gap between them
    candles = [
        create_candle(100, 102, 99, 101, 1000, 10),  # i=0: high=102
        create_candle(101, 103, 100, 102, 1100, 9),  # i=1
        create_candle(102, 105, 103, 104, 1200, 8),  # i=2: low=103, FVG1: 102 < 103
        create_candle(104, 106, 103, 105, 1300, 7),  # i=3
        create_candle(105, 107, 104, 106, 1400, 6),  # i=4: high=107
        create_candle(106, 108, 105, 107, 1500, 5),  # i=5
        create_candle(107, 110, 109, 109.5, 1600, 4),  # i=6: low=109, FVG2: 107 < 109
    ]

    fvgs = detector.merge_fvgs(detector.detect_fvgs(candles))

    # Two non-overlapping FVGs
    assert len(fvgs) == 2
    assert fvgs[0].bottom == 102.0
    assert fvgs[0].top == 103.0
    assert fvgs[1].bottom == 107.0
    assert fvgs[1].top == 109.0


def test_fvg_merging_overlapping():
    """Overlapping FVGs should be merged."""
    from src.scanner.indicators.patterns.fvg import FVGZone

    detector = FVGDetector()

    # Manually create overlapping FVGs for clearer test
    fvgs = [
        FVGZone(top=105.0, bottom=100.0, bullish=True, candle_index=0),  # 100-105
        FVGZone(top=103.0, bottom=102.0, bullish=True, candle_index=3),  # 102-103 (inside first)
    ]

    merged = detector.merge_fvgs(fvgs)

    assert len(merged) == 1
    assert merged[0].bottom == 100.0
    assert merged[0].top == 105.0


def test_fvg_mitigation_bullish():
    """Bullish FVG is mitigated when price closes below the zone bottom."""
    from src.scanner.indicators.patterns.fvg import FVGZone

    detector = FVGDetector()

    # FVG from 100-102 (bullish gap up)
    fvg = FVGZone(top=102.0, bottom=100.0, bullish=True, candle_index=0)

    # Candles after FVG: price drops and closes below 100
    candles = [
        create_candle(102, 104, 101, 103, 1000, 5),  # Inside FVG
        create_candle(103, 105, 98, 99, 1200, 4),  # Close at 99 (< 100) → mitigated!
        create_candle(99, 101, 97, 98, 1300, 3),
    ]

    mitigated = detector.check_mitigation(fvg, candles)

    assert mitigated is True


def test_fvg_mitigation_bearish():
    """Bearish FVG is mitigated when price closes above the zone top."""
    from src.scanner.indicators.patterns.fvg import FVGZone

    detector = FVGDetector()

    # FVG from 102-100 (bearish gap down)
    fvg = FVGZone(top=102.0, bottom=100.0, bullish=False, candle_index=0)

    # Candles after FVG: price rises and closes above 102
    candles = [
        create_candle(101, 102, 99, 100.5, 1000, 5),  # Inside FVG
        create_candle(100.5, 103, 100, 102.5, 1200, 4),  # Close at 102.5 (> 102) → mitigated!
        create_candle(102.5, 104, 102, 103, 1300, 3),
    ]

    mitigated = detector.check_mitigation(fvg, candles)

    assert mitigated is True


def test_fvg_not_mitigated():
    """FVG remains unmitigated if price never closes through it."""
    from src.scanner.indicators.patterns.fvg import FVGZone

    detector = FVGDetector()

    # Bullish FVG from 100-102
    fvg = FVGZone(top=102.0, bottom=100.0, bullish=True, candle_index=0)

    # Price stays above FVG bottom
    candles = [
        create_candle(102, 104, 101, 103, 1000, 5),
        create_candle(103, 105, 102, 104, 1200, 4),
        create_candle(104, 106, 103, 105, 1300, 3),
    ]

    mitigated = detector.check_mitigation(fvg, candles)

    assert mitigated is False
