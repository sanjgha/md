"""Unit tests for SmartMoneyScanner."""

from src.scanner.scanners.smart_money import SmartMoneyScanner
from src.scanner.context import ScanContext
from src.data_provider.base import Candle
from datetime import datetime, timedelta


def create_candle(open_price, high, low, close, volume, days_ago):
    """Helper to create a candle with timestamp days_ago from now."""
    ts = datetime.utcnow() - timedelta(days=days_ago)
    return Candle(timestamp=ts, open=open_price, high=high, low=low, close=close, volume=volume)


def create_mock_context(candles):
    """Create a ScanContext with mock candles."""
    from unittest.mock import Mock
    from src.scanner.indicators.cache import IndicatorCache

    cache = IndicatorCache(indicators_registry={})
    context = Mock(spec=ScanContext)
    context.stock_id = 1
    context.symbol = "TEST"
    context.daily_candles = candles
    context.intraday_candles = {}
    context.indicator_cache = cache

    def get_indicator_side_effect(name, **kwargs):
        return cache.get_or_compute(name, candles, **kwargs)

    context.get_indicator = get_indicator_side_effect

    return context


def test_bos_detection_bullish():
    """Detect bullish BOS when price closes above swing high."""
    scanner = SmartMoneyScanner()

    # Create 100 volatile baseline candles to ensure swing detection
    import random

    random.seed(42)
    candles = []
    price = 100
    for i in range(120, 20, -1):
        change = random.uniform(-3, 3)
        price += change
        high = price + random.uniform(0, 2)
        low = price - random.uniform(0, 2)
        candles.append(create_candle(price, high, low, price, 1000, i))

    # Add the swing high pattern at the end (most recent)
    candles.extend(
        [
            create_candle(20, 25, 15, 20, 1000, 20),
            create_candle(20, 28, 16, 22, 1100, 19),
            create_candle(22, 30, 17, 24, 1200, 18),  # swing high (30)
            create_candle(24, 29, 18, 23, 1300, 17),
            create_candle(23, 28, 12, 20, 1400, 16),
            create_candle(20, 25, 10, 18, 1500, 15),
            create_candle(18, 24, 11, 19, 1600, 14),
            create_candle(19, 26, 15, 22, 1700, 13),
            create_candle(22, 28, 16, 24, 1800, 12),
            create_candle(24, 32, 17, 25, 1900, 11),
            create_candle(25, 35, 20, 33, 2000, 10),  # closes at 33 > 30 (BOS!)
        ]
    )

    context = create_mock_context(candles)

    bos = scanner.detect_bos(context, swing_highs_only=True)

    assert bos is not None
    assert bos["type"] == "bullish"
    assert bos["price"] == 30.0  # The swing high that broke


def test_bos_detection_bearish():
    """Detect bearish BOS when price closes below swing low."""
    scanner = SmartMoneyScanner()

    # Create 100 volatile baseline candles
    import random

    random.seed(42)
    candles = []
    price = 100
    for i in range(120, 20, -1):
        change = random.uniform(-3, 3)
        price += change
        high = price + random.uniform(0, 2)
        low = price - random.uniform(0, 2)
        candles.append(create_candle(price, high, low, price, 1000, i))

    # Add the swing low pattern at the end (most recent)
    candles.extend(
        [
            create_candle(100, 105, 95, 100, 1000, 20),
            create_candle(100, 108, 96, 102, 1100, 19),
            create_candle(102, 110, 97, 104, 1200, 18),
            create_candle(104, 109, 98, 103, 1300, 17),
            create_candle(103, 108, 92, 100, 1400, 16),
            create_candle(100, 105, 90, 98, 1500, 15),  # swing low (90)
            create_candle(98, 104, 91, 99, 1600, 14),
            create_candle(99, 106, 95, 102, 1700, 13),
            create_candle(102, 108, 96, 104, 1800, 12),
            create_candle(104, 112, 97, 105, 1900, 11),
            create_candle(105, 110, 85, 87, 2000, 10),  # closes at 87 < 90 (BOS!)
        ]
    )

    context = create_mock_context(candles)

    bos = scanner.detect_bos(context)

    assert bos is not None
    assert bos["type"] == "bearish"
    assert bos["price"] == 90.0  # The swing low that broke
