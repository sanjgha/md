"""Fixture helpers for generating test data."""

from datetime import datetime, timedelta

from src.data_provider.base import Candle, Quote


def make_daily_candles(n: int = 250, base_price: float = 100.0) -> list:
    """Generate n daily candles with a gentle upward drift."""
    candles = []
    for i in range(n):
        close = base_price + i * 0.1 + (i % 7 - 3) * 0.5
        candles.append(
            Candle(
                timestamp=datetime(2024, 1, 1) + timedelta(days=i),
                open=close - 0.5,
                high=close + 1.0,
                low=close - 1.0,
                close=close,
                volume=1_000_000 + (i % 5) * 100_000,
            )
        )
    return candles


def make_quote(symbol: str = "AAPL", last: float = 150.0) -> Quote:
    """Create a Quote with given last price."""
    return Quote(
        timestamp=datetime.utcnow(),
        bid=last - 0.05,
        ask=last + 0.05,
        bid_size=100,
        ask_size=100,
        last=last,
        open=last - 1,
        high=last + 2,
        low=last - 2,
        close=last,
        volume=5_000_000,
        change=1.0,
        change_pct=0.67,
        week_52_high=180.0,
        week_52_low=120.0,
        status="active",
    )
