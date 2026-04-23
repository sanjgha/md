"""Unit tests for QuoteWorker."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone
from src.workers.quote_worker import QuoteWorker
from src.data_provider.base import Quote


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
    """Should aggregate unique symbols from all watchlists."""
    worker = QuoteWorker(mock_db_session, mock_cache_service, mock_provider)

    # Mock query to return symbols directly (Stock.symbol)
    mock_row1 = MagicMock()
    mock_row1.symbol = "AAPL"
    mock_row2 = MagicMock()
    mock_row2.symbol = "MSFT"
    mock_row3 = MagicMock()
    mock_row3.symbol = "AAPL"  # Duplicate

    mock_db_session.query.return_value.join.return_value.all.return_value = [
        mock_row1,
        mock_row2,
        mock_row3,
    ]

    symbols = worker._get_all_symbols()

    assert set(symbols) == {"AAPL", "MSFT"}


def test_poll_during_market_hours(mock_db_session, mock_cache_service, mock_provider):
    """Should fetch and cache quotes during market hours."""
    worker = QuoteWorker(mock_db_session, mock_cache_service, mock_provider)

    # Mock market hours as open
    with patch("src.workers.quote_worker.is_market_open", return_value=True):
        # Mock symbols
        with patch.object(worker, "_get_all_symbols", return_value=["AAPL"]):
            # Mock batch fetch
            with patch("src.workers.quote_worker.get_realtime_quotes_batch") as mock_fetch:
                mock_fetch.return_value = [
                    Quote(
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
                ]

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
