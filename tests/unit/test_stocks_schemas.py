"""Unit tests for stocks schemas."""

import pytest
from pydantic import ValidationError

from src.api.stocks.schemas import CandleResponse, CandlesResponse


def test_candle_response_valid():
    """Test valid candle response."""
    candle_data = {
        "time": "2026-04-16T09:30:00",
        "open": 180.20,
        "high": 188.40,
        "low": 179.80,
        "close": 186.59,
        "volume": 52300000,
    }
    candle = CandleResponse(**candle_data)
    assert candle.open == 180.20
    assert candle.close == 186.59


def test_candle_response_validation_fails_on_negative_price():
    """Test that negative prices are rejected."""
    with pytest.raises(ValidationError):
        CandleResponse(
            time="2026-04-16T09:30:00",
            open=-10.0,
            high=188.40,
            low=179.80,
            close=186.59,
            volume=52300000,
        )


def test_candles_response_empty_array():
    """Test empty candles response."""
    response = CandlesResponse()
    assert response.candles == []
