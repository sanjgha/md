"""Unit tests for DataFetcher helper methods."""

from datetime import datetime
from unittest.mock import Mock, MagicMock


from src.data_fetcher.fetcher import DataFetcher
from src.data_provider.base import Candle


def _make_fetcher():
    return DataFetcher(provider=Mock(), db=MagicMock(), rate_limit_delay=0)


def test_detect_corporate_action_forward_split():
    """2:1 forward split (50% price drop overnight) is flagged."""
    fetcher = _make_fetcher()
    candles = [
        Candle(datetime(2024, 1, 1), 100.0, 102.0, 99.0, 100.0, 1_000_000),
        Candle(datetime(2024, 1, 2), 50.0, 51.0, 49.5, 50.0, 2_000_000),  # post-split open
    ]
    assert fetcher._detect_corporate_action("AAPL", candles) is True


def test_detect_corporate_action_reverse_split_1_for_10():
    """1:10 reverse split (900% price jump overnight) is flagged."""
    fetcher = _make_fetcher()
    candles = [
        Candle(datetime(2024, 1, 1), 1.0, 1.1, 0.9, 1.0, 5_000_000),
        Candle(datetime(2024, 1, 2), 10.0, 10.5, 9.8, 10.0, 500_000),  # post-reverse-split open
    ]
    assert fetcher._detect_corporate_action("LOWP", candles) is True


def test_detect_corporate_action_reverse_split_1_for_20():
    """1:20 reverse split (1900% price jump overnight) is flagged."""
    fetcher = _make_fetcher()
    candles = [
        Candle(datetime(2024, 1, 1), 0.5, 0.55, 0.45, 0.5, 10_000_000),
        Candle(datetime(2024, 1, 2), 10.0, 10.2, 9.8, 10.0, 500_000),
    ]
    assert fetcher._detect_corporate_action("PENNY", candles) is True


def test_detect_corporate_action_normal_move():
    """Normal 2% daily move is not flagged."""
    fetcher = _make_fetcher()
    candles = [
        Candle(datetime(2024, 1, 1), 150.0, 152.0, 149.0, 151.0, 1_000_000),
        Candle(datetime(2024, 1, 2), 151.5, 153.0, 150.5, 152.0, 900_000),
    ]
    assert fetcher._detect_corporate_action("AAPL", candles) is False


def test_detect_corporate_action_earnings_gap_under_threshold():
    """30% earnings gap (just under threshold) is not flagged."""
    fetcher = _make_fetcher()
    candles = [
        Candle(datetime(2024, 1, 1), 100.0, 102.0, 99.0, 100.0, 1_000_000),
        Candle(datetime(2024, 1, 2), 130.0, 132.0, 129.0, 131.0, 3_000_000),  # +30% gap
    ]
    assert fetcher._detect_corporate_action("EARN", candles) is False


def test_detect_corporate_action_single_candle():
    """Single candle returns False — nothing to compare."""
    fetcher = _make_fetcher()
    candles = [Candle(datetime(2024, 1, 1), 100.0, 102.0, 99.0, 100.0, 1_000_000)]
    assert fetcher._detect_corporate_action("AAPL", candles) is False


def test_detect_corporate_action_empty():
    """Empty candle list returns False."""
    fetcher = _make_fetcher()
    assert fetcher._detect_corporate_action("AAPL", []) is False


def test_detect_corporate_action_at_threshold_boundary():
    """34% gap (just below threshold) is not flagged (threshold is strict >35%)."""
    fetcher = _make_fetcher()
    candles = [
        Candle(datetime(2024, 1, 1), 100.0, 102.0, 99.0, 100.0, 1_000_000),
        Candle(datetime(2024, 1, 2), 134.0, 135.0, 133.0, 134.0, 1_000_000),  # 34% gap
    ]
    assert fetcher._detect_corporate_action("EDGE", candles) is False


def test_detect_corporate_action_zero_close_skipped():
    """Zero close on prev candle is skipped without ZeroDivisionError."""
    fetcher = _make_fetcher()
    candles = [
        Candle(datetime(2024, 1, 1), 0.0, 0.0, 0.0, 0.0, 0),
        Candle(datetime(2024, 1, 2), 100.0, 102.0, 99.0, 100.0, 1_000_000),
    ]
    assert fetcher._detect_corporate_action("ZERO", candles) is False


def test_sync_daily_preloads_stock_map_with_one_query():
    """sync_daily issues exactly one DB query to load the stock map, not one per symbol."""
    mock_db = MagicMock()
    # Mock the stock_map query: query(Stock).all() returns empty list
    mock_db.query.return_value.all.return_value = []

    fetcher = DataFetcher(provider=Mock(), db=mock_db, rate_limit_delay=0)
    fetcher.sync_daily(symbols=["AAPL", "MSFT", "GOOGL"])

    # query() should be called once for the preload, not 3 times for symbol lookups
    assert mock_db.query.call_count == 1
