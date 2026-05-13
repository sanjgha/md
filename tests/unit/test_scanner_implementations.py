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


def test_executor_loads_benchmark_candles_once_per_run(monkeypatch):
    """Verify ScannerExecutor.run_eod calls the benchmark-loader once, not per stock."""
    from src.scanner.executor import ScannerExecutor
    from src.scanner.registry import ScannerRegistry
    from src.output.base import OutputHandler

    class NullOutput(OutputHandler):
        def emit_scan_result(self, result):
            pass

        def emit_alert(self, alert):
            pass

    call_counter = {"count": 0}

    def fake_load_benchmark(self, symbol="SPY"):
        call_counter["count"] += 1
        return []

    monkeypatch.setattr(ScannerExecutor, "_load_benchmark_candles", fake_load_benchmark)

    executor = ScannerExecutor(
        registry=ScannerRegistry(),
        indicators_registry={},
        output_handler=NullOutput(),
        db=None,
    )
    stocks = {1: ("AAA", []), 2: ("BBB", []), 3: ("CCC", [])}
    executor.run_eod(stocks)
    assert call_counter["count"] == 1


def test_executor_passes_benchmark_candles_into_context(monkeypatch):
    """Verify the benchmark candles loaded once are passed into every per-stock context."""
    from datetime import datetime
    from src.data_provider.base import Candle
    from src.scanner.base import Scanner
    from src.scanner.executor import ScannerExecutor
    from src.scanner.registry import ScannerRegistry
    from src.output.base import OutputHandler

    class CapturingScanner(Scanner):
        captured: list = []

        def scan(self, context):
            CapturingScanner.captured.append(len(context.benchmark_candles))
            return []

    class NullOutput(OutputHandler):
        def emit_scan_result(self, result):
            pass

        def emit_alert(self, alert):
            pass

    spy = [
        Candle(timestamp=datetime(2025, 1, i + 1), open=100, high=100, low=100, close=100, volume=1)
        for i in range(5)
    ]
    monkeypatch.setattr(ScannerExecutor, "_load_benchmark_candles", lambda self, symbol="SPY": spy)

    CapturingScanner.captured = []  # reset class-level list
    registry = ScannerRegistry()
    registry.register("capturing", CapturingScanner())
    executor = ScannerExecutor(
        registry=registry, indicators_registry={}, output_handler=NullOutput(), db=None
    )
    executor.run_eod({1: ("AAA", []), 2: ("BBB", [])})
    assert CapturingScanner.captured == [5, 5]
