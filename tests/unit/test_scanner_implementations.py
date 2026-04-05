# tests/unit/test_scanner_implementations.py
from datetime import datetime, timedelta
from src.scanner.scanners.price_action import PriceActionScanner
from src.scanner.scanners.momentum_scan import MomentumScanner
from src.scanner.scanners.volume_scan import VolumeScanner
from src.scanner.context import ScanContext
from src.scanner.indicators.cache import IndicatorCache
from src.scanner.indicators.moving_averages import SMA
from src.scanner.indicators.momentum import RSI
from src.data_provider.base import Candle


def make_scan_context(symbol="AAPL", closes=None, volumes=None):
    if closes is None:
        closes = [100 + i * 0.5 for i in range(220)]
    if volumes is None:
        volumes = [1_000_000] * len(closes)

    base = datetime(2024, 1, 1)
    candles = [
        Candle(base + timedelta(days=i), c, c + 1, c - 1, c, v)
        for i, (c, v) in enumerate(zip(closes, volumes))
    ]
    indicators = {"sma": SMA(), "rsi": RSI()}
    return ScanContext(
        stock_id=1,
        symbol=symbol,
        daily_candles=candles,
        intraday_candles={},
        indicator_cache=IndicatorCache(indicators),
    )


def test_price_action_scanner_returns_list():
    context = make_scan_context()
    scanner = PriceActionScanner()
    results = scanner.scan(context)
    assert isinstance(results, list)


def test_price_action_scanner_too_few_candles():
    context = make_scan_context(closes=[100.0] * 10)
    scanner = PriceActionScanner()
    results = scanner.scan(context)
    assert results == []


def test_momentum_scanner_returns_list():
    context = make_scan_context()
    scanner = MomentumScanner()
    results = scanner.scan(context)
    assert isinstance(results, list)


def test_momentum_scanner_too_few_candles():
    context = make_scan_context(closes=[100.0] * 10)
    scanner = MomentumScanner()
    results = scanner.scan(context)
    assert results == []


def test_volume_scanner_detects_spike():
    base_vol = 1_000_000
    closes = [100.0] * 21
    volumes = [base_vol] * 20 + [base_vol * 3]
    context = make_scan_context(closes=closes, volumes=volumes)
    scanner = VolumeScanner()
    results = scanner.scan(context)
    assert len(results) == 1
    assert results[0].metadata["ratio"] == 3.0


def test_volume_scanner_no_spike():
    closes = [100.0] * 21
    volumes = [1_000_000] * 21
    context = make_scan_context(closes=closes, volumes=volumes)
    scanner = VolumeScanner()
    results = scanner.scan(context)
    assert results == []


def test_volume_scanner_too_few_candles():
    context = make_scan_context(closes=[100.0] * 10)
    scanner = VolumeScanner()
    results = scanner.scan(context)
    assert results == []
