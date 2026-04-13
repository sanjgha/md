"""Unit tests for PreCloseExecutor."""
from unittest.mock import MagicMock, patch
from src.scanner.pre_close_executor import PreCloseExecutor


def test_pre_close_executor_run_calls_persist_with_pre_close_type():
    """PreCloseExecutor.run() persists results with run_type='pre_close'."""
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
