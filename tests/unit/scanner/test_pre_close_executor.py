"""Unit tests for PreCloseExecutor."""
from unittest.mock import MagicMock, patch
from src.scanner.pre_close_executor import PreCloseExecutor
from src.scanner.base import ScanResult


def test_pre_close_executor_run_returns_empty_when_no_stocks():
    """PreCloseExecutor.run() returns empty list when no stocks found."""
    db = MagicMock()
    db.query.return_value.all.return_value = []  # no stocks = no results
    registry = MagicMock()
    registry.list.return_value = {}
    output_handler = MagicMock()

    executor = PreCloseExecutor(
        registry=registry,
        indicators_registry={},
        output_handler=output_handler,
        db=db,
    )
    results = executor.run()

    assert results == []
    # With no stocks, no DB writes should occur
    db.add_all.assert_not_called()


def test_pre_close_executor_build_contexts_skips_stocks_without_quotes():
    """PreCloseExecutor.build_contexts() skips stocks with no realtime quote."""
    from src.db.models import Stock, RealtimeQuote

    stock = MagicMock(spec=Stock)
    stock.id = 1
    stock.symbol = "AAPL"
    stock.daily_candles = []

    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        if model == Stock:
            q.all.return_value = [stock]
        elif model == RealtimeQuote:
            q.filter.return_value.order_by.return_value.first.return_value = None
        return q

    db.query.side_effect = query_side_effect

    registry = MagicMock()
    output_handler = MagicMock()

    executor = PreCloseExecutor(
        registry=registry,
        indicators_registry={},
        output_handler=output_handler,
        db=db,
    )
    contexts = executor.build_contexts()
    assert contexts == []


def test_pre_close_executor_persists_with_pre_close_run_type():
    """PreCloseExecutor.run() calls _persist_results with run_type='pre_close'."""
    from src.db.models import Stock, RealtimeQuote

    # Create a mock stock with a realtime quote
    stock = MagicMock(spec=Stock)
    stock.id = 1
    stock.symbol = "AAPL"
    stock.daily_candles = []

    # Create a mock realtime quote
    quote = MagicMock(spec=RealtimeQuote)
    quote.timestamp = None
    quote.open = 100.0
    quote.high = 102.0
    quote.low = 99.0
    quote.last = 101.0
    quote.volume = 1000000

    db = MagicMock()

    def query_side_effect(model):
        q = MagicMock()
        if model == Stock:
            q.all.return_value = [stock]
        elif model == RealtimeQuote:
            q.filter.return_value.order_by.return_value.first.return_value = quote
        return q

    db.query.side_effect = query_side_effect

    registry = MagicMock()
    output_handler = MagicMock()

    executor = PreCloseExecutor(
        registry=registry,
        indicators_registry={},
        output_handler=output_handler,
        db=db,
    )

    # Create a mock scan result
    mock_result = MagicMock(spec=ScanResult)

    # Patch the registry to return one scanner that returns a result
    mock_scanner = MagicMock()
    mock_scanner.scan.return_value = [mock_result]
    registry.list.return_value = {"mock_scanner": mock_scanner}

    with patch.object(executor, "_persist_results") as mock_persist:
        results = executor.run()

    # Verify _persist_results was called with run_type="pre_close"
    mock_persist.assert_called_once()
    call_args = mock_persist.call_args
    assert call_args.kwargs.get("run_type") == "pre_close"
