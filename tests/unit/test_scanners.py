# tests/unit/test_scanners.py
from src.scanner.base import Scanner, ScanResult
from src.scanner.context import ScanContext
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
