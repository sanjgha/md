# tests/unit/test_output_handlers.py
import logging
from datetime import datetime
from unittest.mock import MagicMock
from src.scanner.base import ScanResult
from src.output.base import Alert
from src.output.cli import CLIOutputHandler
from src.output.composite import CompositeOutputHandler
from src.data_provider.base import Quote


def make_quote():
    return Quote(
        timestamp=datetime.now(),
        bid=100.0,
        ask=100.5,
        bid_size=100,
        ask_size=100,
        last=100.2,
        open=99.5,
        high=101,
        low=99,
        close=100,
        volume=1000000,
        change=0.5,
        change_pct=0.5,
        week_52_high=120,
        week_52_low=80,
        status="active",
    )


def test_alert_dataclass():
    alert = Alert(ticker="AAPL", reason="test", quote=make_quote())
    assert alert.ticker == "AAPL"
    assert alert.timestamp is not None


def test_cli_handler_emit_does_not_raise(capsys):
    handler = CLIOutputHandler()
    result = ScanResult(stock_id=1, scanner_name="test", metadata={"key": "val"})
    handler.emit_scan_result(result)
    captured = capsys.readouterr()
    assert "test" in captured.out


def test_cli_handler_emit_alert(capsys):
    handler = CLIOutputHandler()
    alert = Alert(ticker="AAPL", reason="target_reached", quote=make_quote())
    handler.emit_alert(alert)
    captured = capsys.readouterr()
    assert "AAPL" in captured.out


def test_composite_handler_delegates_to_all():
    h1, h2 = MagicMock(), MagicMock()
    h1.emit_scan_result = MagicMock()
    h2.emit_scan_result = MagicMock()
    composite = CompositeOutputHandler([h1, h2])
    result = ScanResult(stock_id=1, scanner_name="test", metadata={})
    composite.emit_scan_result(result)
    h1.emit_scan_result.assert_called_once_with(result)
    h2.emit_scan_result.assert_called_once_with(result)


def test_composite_handler_logs_exception_not_silently_swallows(caplog):
    failing = MagicMock()
    failing.emit_scan_result.side_effect = RuntimeError("handler crashed")
    composite = CompositeOutputHandler([failing])
    result = ScanResult(stock_id=1, scanner_name="test", metadata={})
    with caplog.at_level(logging.ERROR):
        composite.emit_scan_result(result)
    assert "handler crashed" in caplog.text or "failed" in caplog.text.lower()
