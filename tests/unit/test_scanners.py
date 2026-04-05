# tests/unit/test_scanners.py
import datetime

from src.data_provider.base import Candle
from src.output.cli import CLIOutputHandler
from src.scanner.base import Scanner, ScanResult
from src.scanner.context import ScanContext
from src.scanner.executor import ScannerExecutor
from src.scanner.indicators.moving_averages import SMA
from src.scanner.registry import ScannerRegistry


def test_scan_result_dataclass():
    result = ScanResult(stock_id=1, scanner_name="test_scanner", metadata={"reason": "test"})
    assert result.stock_id == 1
    assert result.scanner_name == "test_scanner"
    assert result.matched_at is not None


def test_scanner_registry_registration():
    registry = ScannerRegistry()

    class TestScanner(Scanner):
        def scan(self, context: ScanContext):
            return []

    registry.register("test", TestScanner())
    assert registry.get("test") is not None


def test_scanner_registry_list_empty():
    registry = ScannerRegistry()
    assert len(registry.list()) == 0


def test_scanner_registry_multiple():
    registry = ScannerRegistry()

    class NoopScanner(Scanner):
        def scan(self, context: ScanContext):
            return []

    registry.register("a", NoopScanner())
    registry.register("b", NoopScanner())
    assert len(registry.list()) == 2


class AlwaysMatchScanner(Scanner):
    """Scanner that always matches every stock."""

    def scan(self, context: ScanContext):
        """Return a match for every stock."""
        return [ScanResult(stock_id=context.stock_id, scanner_name="always", metadata={})]


def make_candles_list(n=10):
    """Create a list of n candles starting from 2024-01-01."""
    return [
        Candle(
            datetime.datetime(2024, 1, 1) + datetime.timedelta(days=i),
            100 + i,
            102 + i,
            99 + i,
            101 + i,
            1000,
        )
        for i in range(n)
    ]


def test_executor_run_eod_returns_results():
    registry = ScannerRegistry()
    registry.register("always", AlwaysMatchScanner())
    indicators = {"sma": SMA()}
    output = CLIOutputHandler()
    executor = ScannerExecutor(
        registry=registry, indicators_registry=indicators, output_handler=output, db=None
    )
    stocks = {1: ("AAPL", make_candles_list(50))}
    results = executor.run_eod(stocks)
    assert len(results) == 1
    assert results[0].scanner_name == "always"


def test_executor_to_candles_conversion():
    registry = ScannerRegistry()
    output = CLIOutputHandler()
    executor = ScannerExecutor(
        registry=registry, indicators_registry={}, output_handler=output, db=None
    )

    class FakeOrmCandle:
        """Fake ORM candle with string numeric fields."""

        def __init__(self):
            """Initialize with string numeric values."""
            self.timestamp = datetime.datetime(2024, 1, 1)
            self.open = "100.00"
            self.high = "102.00"
            self.low = "99.00"
            self.close = "101.00"
            self.volume = "1000000"

    orm_candles = [FakeOrmCandle()]
    candles = executor._to_candles(orm_candles)
    assert len(candles) == 1
    assert isinstance(candles[0].close, float)
    assert isinstance(candles[0].volume, int)
