"""Unit tests for QuoteWorker."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from src.workers.quote_worker import QuoteWorker
from src.data_provider.base import Quote
from src.db.models import RealtimeQuote


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    return MagicMock()


@pytest.fixture
def mock_cache_service():
    """Mock quote cache service."""
    return MagicMock()


@pytest.fixture
def mock_provider():
    """Mock data provider."""
    provider = Mock()
    provider.base_url = "https://api.test.com"
    return provider


def test_get_all_unique_symbols_from_watchlists(mock_db_session):
    """Should aggregate unique symbols from all watchlists (deduplicating via .distinct())."""
    worker = QuoteWorker(mock_db_session, mock_cache_service, mock_provider)

    # Mock query chain: query().join().distinct().all()
    mock_row1 = MagicMock()
    mock_row1.symbol = "AAPL"
    mock_row2 = MagicMock()
    mock_row2.symbol = "MSFT"

    mock_db_session.query.return_value.join.return_value.distinct.return_value.all.return_value = [
        mock_row1,
        mock_row2,
    ]

    symbols = worker._get_all_symbols()

    assert symbols == ["AAPL", "MSFT"]
    assert len(symbols) == 2


def test_poll_during_market_hours(mock_db_session, mock_cache_service, mock_provider):
    """Should fetch and cache quotes during market hours."""
    worker = QuoteWorker(mock_db_session, mock_cache_service, mock_provider)

    # Mock market hours as open
    with patch("src.workers.quote_worker.is_market_open", return_value=True):
        # Mock symbols
        with patch.object(worker, "_get_all_symbols", return_value=["AAPL"]):
            # Mock batch fetch — returns dict[str, Quote]
            with patch("src.workers.quote_worker.get_realtime_quotes_batch") as mock_fetch:
                mock_fetch.return_value = {
                    "AAPL": Quote(
                        timestamp=datetime.now(timezone.utc),
                        bid=149.5,
                        ask=150.5,
                        bid_size=100,
                        ask_size=150,
                        last=150.0,
                        volume=1000000,
                        change=1.0,
                        change_pct=0.67,
                    )
                }

                result = worker.poll()

                # Verify quotes were fetched
                assert result == 1
                # Verify cache was updated
                mock_cache_service.refresh_cache.assert_called_once()
                # Verify call contains correct quote
                call_args = mock_cache_service.refresh_cache.call_args[0][0]
                assert len(call_args) == 1
                assert call_args[0].symbol == "AAPL"
                assert call_args[0].last == 150.0


def test_poll_when_market_closed(mock_db_session, mock_cache_service, mock_provider):
    """Should skip polling when market is closed."""
    worker = QuoteWorker(mock_db_session, mock_cache_service, mock_provider)

    # Mock market hours as closed
    with patch("src.workers.quote_worker.is_market_open", return_value=False):
        result = worker.poll()

        # Verify no quotes were fetched
        assert result == 0
        # Verify cache was not updated
        mock_cache_service.refresh_cache.assert_not_called()


def test_poll_with_no_symbols(mock_db_session, mock_cache_service, mock_provider):
    """Should handle empty watchlist gracefully."""
    worker = QuoteWorker(mock_db_session, mock_cache_service, mock_provider)

    with patch("src.workers.quote_worker.is_market_open", return_value=True):
        with patch.object(worker, "_get_all_symbols", return_value=[]):
            result = worker.poll()

            # Verify no quotes were fetched
            assert result == 0
            # Verify cache was not updated
            mock_cache_service.refresh_cache.assert_not_called()


def test_poll_handles_exceptions(mock_db_session, mock_cache_service, mock_provider):
    """Should return 0 on exception during polling."""
    worker = QuoteWorker(mock_db_session, mock_cache_service, mock_provider)

    with patch("src.workers.quote_worker.is_market_open", return_value=True):
        with patch.object(worker, "_get_all_symbols", side_effect=Exception("DB error")):
            result = worker.poll()

            # Verify error was handled gracefully
            assert result == 0
            # Verify cache was not updated
            mock_cache_service.refresh_cache.assert_not_called()


def test_poll_caches_none_when_high_low_are_zero(
    mock_db_session, mock_cache_service, mock_provider
):
    """When API omits high/low (defaults to 0.0), cache must store None — not 0.0.

    0.0 === 0.0 in the frontend RangeBar makes every stock show the same 50% center marker.
    """
    worker = QuoteWorker(mock_db_session, mock_cache_service, mock_provider)

    with patch("src.workers.quote_worker.is_market_open", return_value=True):
        with patch.object(worker, "_get_all_symbols", return_value=["AAPL"]):
            with patch("src.workers.quote_worker.get_realtime_quotes_batch") as mock_fetch:
                mock_fetch.return_value = {
                    "AAPL": Quote(
                        timestamp=datetime.now(timezone.utc),
                        bid=149.5,
                        ask=150.5,
                        bid_size=100,
                        ask_size=150,
                        last=150.0,
                        volume=1000000,
                        change=1.0,
                        change_pct=0.67,
                        high=0.0,  # API omitted "high" key → default 0.0
                        low=0.0,  # API omitted "low" key → default 0.0
                    )
                }

                worker.poll()

                call_args = mock_cache_service.refresh_cache.call_args[0][0]
                assert len(call_args) == 1
                assert call_args[0].high is None, "high=0.0 must be stored as None in cache"
                assert call_args[0].low is None, "low=0.0 must be stored as None in cache"


def test_store_quotes_stores_none_when_high_low_are_zero(mock_db_session):
    """_store_quotes must write None (not 0.0) for high/low to the DB when value is 0."""
    worker = QuoteWorker(mock_db_session, MagicMock(), Mock())

    # Mock the stock ID lookup query
    mock_stock_row = MagicMock()
    mock_stock_row.symbol = "AAPL"
    mock_stock_row.id = 1
    mock_db_session.query.return_value.filter.return_value.all.return_value = [mock_stock_row]

    quote = Quote(
        timestamp=datetime(2024, 5, 1, 12, 0, 0),
        bid=149.5,
        ask=150.5,
        bid_size=100,
        ask_size=150,
        last=150.0,
        volume=1000000,
        change=1.0,
        change_pct=0.67,
        high=0.0,
        low=0.0,
    )

    worker._store_quotes({"AAPL": quote})

    added = [call.args[0] for call in mock_db_session.add.call_args_list]
    rt_quotes = [obj for obj in added if isinstance(obj, RealtimeQuote)]
    assert len(rt_quotes) == 1, "Expected one RealtimeQuote to be added to DB"
    assert rt_quotes[0].high is None, "high=0.0 must be stored as None in DB"
    assert rt_quotes[0].low is None, "low=0.0 must be stored as None in DB"
