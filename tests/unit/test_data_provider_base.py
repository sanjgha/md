"""Tests for abstract DataProvider interface and dataclasses."""

import pytest
from datetime import datetime
from src.data_provider.base import DataProvider, Candle, Quote


def test_candle_dataclass():
    """Candle dataclass stores values correctly."""
    candle = Candle(
        timestamp=datetime(2024, 1, 1),
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=1000000,
    )
    assert candle.close == 101.0


def test_quote_dataclass():
    """Quote dataclass stores all fields."""
    quote = Quote(
        timestamp=datetime(2024, 1, 1),
        bid=100.0,
        ask=100.5,
        bid_size=1000,
        ask_size=1000,
        last=100.2,
        open=99.5,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=5000000,
        change=0.5,
        change_pct=0.5,
        week_52_high=120.0,
        week_52_low=80.0,
        status="active",
    )
    assert quote.bid < quote.ask


def test_data_provider_is_abstract():
    """DataProvider cannot be instantiated directly."""
    with pytest.raises(TypeError):
        DataProvider()
