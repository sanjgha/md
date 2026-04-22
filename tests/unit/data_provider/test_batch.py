"""Tests for async batch quote fetching."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.data_provider.batch import get_realtime_quotes_batch, _fetch_batch_comma_separated
from src.data_provider.base import Quote
from datetime import datetime


@pytest.mark.asyncio
async def test_batch_comma_separated_success():
    """Should successfully fetch quotes using comma-separated request."""
    mock_provider = Mock()
    mock_provider.base_url = "https://api.test.com"

    # Mock successful batch request
    mock_response_data = {
        "s": "ok",
        "symbol": ["AAPL", "MSFT"],
        "last": [150.0, 250.0],
        "change": [1.0, 2.0],
        "changepct": [0.67, 0.8],
        "updated": [1714560000, 1714560000],
        "bid": [149.5, 249.5],
        "ask": [150.5, 250.5],
        "bidSize": [100, 200],
        "askSize": [150, 250],
        "volume": [1000000, 2000000],
    }

    with patch("src.data_provider.batch.aiohttp.ClientSession") as mock_session_cls:
        # Create mock response
        mock_response = AsyncMock()
        mock_response.json = AsyncMock(return_value=mock_response_data)
        mock_response.raise_for_status = Mock()

        # Create mock get request
        mock_get = AsyncMock(return_value=mock_response)
        mock_get.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get.__aexit__ = AsyncMock()

        # Create mock session
        mock_session = AsyncMock()
        mock_session.get = Mock(return_value=mock_get)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock()

        mock_session_cls.return_value = mock_session

        result = await _fetch_batch_comma_separated(mock_provider, ["AAPL", "MSFT"])

        assert len(result) == 2
        assert result[0].bid == 149.5
        assert result[1].bid == 249.5
        assert result[0].last == 150.0
        assert result[1].last == 250.0


@pytest.mark.asyncio
async def test_batch_empty_symbols():
    """Should return empty list for empty symbols."""
    mock_provider = Mock()

    result = await get_realtime_quotes_batch(mock_provider, [])

    assert result == []


@pytest.mark.asyncio
async def test_batch_fallback_to_parallel():
    """Should fall back to parallel requests when batch fails."""
    mock_provider = Mock()
    mock_provider.base_url = "https://api.test.com"

    # Mock parallel mode success
    mock_provider.get_realtime_quote = Mock(
        side_effect=[
            Quote(
                timestamp=datetime(2024, 5, 1, 12, 0, 0),
                bid=149.5,
                ask=150.5,
                bid_size=100,
                ask_size=150,
                last=150.0,
                volume=1000000,
                change=1.0,
                change_pct=0.67,
            ),
            Quote(
                timestamp=datetime(2024, 5, 1, 12, 0, 0),
                bid=249.5,
                ask=250.5,
                bid_size=200,
                ask_size=250,
                last=250.0,
                volume=2000000,
                change=2.0,
                change_pct=0.8,
            ),
        ]
    )

    with patch(
        "src.data_provider.batch._fetch_batch_comma_separated",
        side_effect=Exception("Batch failed"),
    ):
        result = await get_realtime_quotes_batch(mock_provider, ["AAPL", "MSFT"])

        assert len(result) == 2
        assert result[0].bid == 149.5
        assert result[1].bid == 249.5
