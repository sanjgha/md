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


def test_momentum_scanner_detects_oversold():
    # Alternating down then flat produces low RSI on final value
    closes = [100.0 - i * 0.5 for i in range(60)]  # steadily falling → oversold
    context = make_scan_context(closes=closes)
    scanner = MomentumScanner()
    results = scanner.scan(context)
    assert len(results) == 1
    assert results[0].metadata["reason"] == "oversold"
    assert results[0].metadata["rsi"] < 30


def test_momentum_scanner_no_match_neutral():
    # Alternating up/down keeps RSI near 50
    closes = [100.0 + (1 if i % 2 == 0 else -1) for i in range(60)]
    context = make_scan_context(closes=closes)
    scanner = MomentumScanner()
    results = scanner.scan(context)
    assert results == []


def test_price_action_no_match_when_sma50_below_sma200():
    # Steadily declining prices → SMA50 < SMA200
    closes = [200.0 - i * 0.3 for i in range(220)]
    context = make_scan_context(closes=closes)
    scanner = PriceActionScanner()
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


def test_scan_context_defaults_benchmark_candles_to_empty_list():
    """Existing scanners that don't pass benchmark_candles should still construct cleanly."""
    from src.scanner.context import ScanContext
    from src.scanner.indicators.cache import IndicatorCache

    ctx = ScanContext(
        stock_id=1,
        symbol="AAPL",
        daily_candles=[],
        intraday_candles={},
        indicator_cache=IndicatorCache({}),
    )
    assert ctx.benchmark_candles == []


def test_scan_context_accepts_benchmark_candles():
    from datetime import datetime
    from src.data_provider.base import Candle
    from src.scanner.context import ScanContext
    from src.scanner.indicators.cache import IndicatorCache

    spy_candles = [
        Candle(timestamp=datetime(2025, 1, 1), open=100, high=100, low=100, close=100, volume=1)
    ]
    ctx = ScanContext(
        stock_id=1,
        symbol="AAPL",
        daily_candles=[],
        intraday_candles={},
        indicator_cache=IndicatorCache({}),
        benchmark_candles=spy_candles,
    )
    assert len(ctx.benchmark_candles) == 1
    assert ctx.benchmark_candles[0].close == 100
