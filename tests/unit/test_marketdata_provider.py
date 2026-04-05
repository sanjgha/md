"""Tests for MarketData.app provider implementation."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from src.data_provider.marketdata_app import MarketDataAppProvider
from src.data_provider.exceptions import SymbolNotFoundError, DataProviderError


def test_marketdata_provider_init():
    """Provider initializes with correct base URL."""
    provider = MarketDataAppProvider(api_token="test_token", max_retries=3, retry_backoff_base=0)
    assert provider.api_token == "test_token"
    assert provider.base_url == "https://api.marketdata.app/v1"


def test_validate_symbol_called_on_get_daily_candles():
    """Invalid symbol raises SymbolNotFoundError before any HTTP call."""
    provider = MarketDataAppProvider(api_token="test_token", max_retries=1, retry_backoff_base=0)
    with pytest.raises(SymbolNotFoundError):
        provider.get_daily_candles("invalid!", datetime(2024, 1, 1), datetime(2024, 1, 31))


def test_validate_resolution_called_on_get_intraday():
    """Invalid resolution raises DataProviderError before any HTTP call."""
    provider = MarketDataAppProvider(api_token="test_token", max_retries=1, retry_backoff_base=0)
    with pytest.raises(DataProviderError):
        provider.get_intraday_candles("AAPL", "1d", datetime(2024, 1, 1), datetime(2024, 1, 31))


@patch("src.data_provider.marketdata_app.requests.Session")
def test_get_daily_candles_parsing(mock_session_class):
    """Daily candles are parsed from JSON response."""
    mock_session = Mock()
    mock_session_class.return_value = mock_session

    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "t": "2024-01-01T00:00:00",
                "o": 150.0,
                "h": 152.0,
                "l": 149.0,
                "c": 151.0,
                "v": 1000000,
            }
        ]
    }
    mock_response.raise_for_status = Mock()
    mock_session.get.return_value = mock_response

    provider = MarketDataAppProvider(api_token="test_token", max_retries=1, retry_backoff_base=0)
    candles = provider.get_daily_candles("AAPL", datetime(2024, 1, 1), datetime(2024, 1, 31))

    assert len(candles) == 1
    assert candles[0].close == 151.0
    call_kwargs = mock_session.get.call_args
    assert call_kwargs[1].get("timeout") == (5, 30)


@patch("src.data_provider.marketdata_app.requests.Session")
def test_request_uses_timeout(mock_session_class):
    """All requests use timeout=(5, 30)."""
    mock_session = Mock()
    mock_session_class.return_value = mock_session
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.raise_for_status = Mock()
    mock_response.json.return_value = {"results": []}
    mock_session.get.return_value = mock_response

    provider = MarketDataAppProvider(api_token="test_token", max_retries=1, retry_backoff_base=0)
    provider.get_daily_candles("AAPL", datetime(2024, 1, 1), datetime(2024, 1, 31))

    call_kwargs = mock_session.get.call_args
    assert call_kwargs[1].get("timeout") == (5, 30)
