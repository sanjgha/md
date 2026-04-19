"""Unit tests for StockService."""

import pytest
from datetime import date, datetime
from sqlalchemy.orm import Session

from src.api.stocks.service import StockService
from src.db.models import DailyCandle, IntradayCandle, Stock


def test_get_candles_5m_routes_to_intraday(db_session: Session):
    """Test that 5m resolution queries intraday_candles."""
    # Create test stock
    stock = Stock(symbol="TEST", name="Test Stock")
    db_session.add(stock)
    db_session.flush()

    # Create test intraday candle
    candle = IntradayCandle(
        stock_id=stock.id,
        resolution="5m",
        timestamp=datetime(2026, 4, 16, 9, 30),
        open=100.0,
        high=105.0,
        low=99.0,
        close=104.0,
        volume=1000,
    )
    db_session.add(candle)
    db_session.commit()

    service = StockService(db_session)
    candles = service.get_candles(
        symbol="TEST",
        resolution="5m",
        start_date=datetime(2026, 4, 16),
        end_date=datetime(2026, 4, 17),
    )

    assert len(candles) == 1
    assert candles[0].open == 100.0


def test_get_candles_invalid_resolution_raises_value_error(db_session: Session):
    """Test that invalid resolution raises ValueError."""
    service = StockService(db_session)

    with pytest.raises(ValueError, match="Invalid resolution"):
        service.get_candles(
            symbol="TEST",
            resolution="invalid",
            start_date=datetime(2026, 4, 16),
            end_date=datetime(2026, 4, 17),
        )


def test_get_candles_exceeds_max_range_raises_value_error(db_session: Session):
    """Test that exceeding max range raises ValueError."""
    service = StockService(db_session)

    with pytest.raises(ValueError, match="exceeds max"):
        service.get_candles(
            symbol="TEST",
            resolution="5m",
            start_date=datetime(2026, 4, 1),
            end_date=datetime(2026, 4, 20),  # 19 days > 7 day max
        )


def test_get_candles_daily_resolution(db_session: Session):
    """Test that D resolution queries daily_candles."""
    stock = Stock(symbol="TEST", name="Test Stock")
    db_session.add(stock)
    db_session.flush()

    candle = DailyCandle(
        stock_id=stock.id,
        timestamp=date(2026, 4, 16),
        open=100.0,
        high=105.0,
        low=99.0,
        close=104.0,
        volume=1000,
    )
    db_session.add(candle)
    db_session.commit()

    service = StockService(db_session)
    candles = service.get_candles(
        symbol="TEST",
        resolution="D",
        start_date=datetime(2026, 4, 16),
        end_date=datetime(2026, 4, 17),
    )

    assert len(candles) == 1
    assert candles[0].open == 100.0


def test_get_candles_unknown_symbol_raises_value_error(db_session: Session):
    """Test that unknown symbol raises ValueError."""
    service = StockService(db_session)

    with pytest.raises(ValueError, match="Stock not found"):
        service.get_candles(
            symbol="UNKNOWN",
            resolution="D",
            start_date=datetime(2026, 4, 16),
            end_date=datetime(2026, 4, 17),
        )


def test_get_candles_timezone_edge_case(db_session: Session):
    """Test that date filtering works correctly across timezone boundaries."""
    stock = Stock(symbol="TEST", name="Test Stock")
    db_session.add(stock)
    db_session.flush()

    # Create candle at midnight UTC (edge case)
    candle = IntradayCandle(
        stock_id=stock.id,
        resolution="5m",
        timestamp=datetime(2026, 4, 16, 0, 0),  # Midnight UTC
        open=100.0,
        high=105.0,
        low=99.0,
        close=104.0,
        volume=1000,
    )
    db_session.add(candle)
    db_session.commit()

    service = StockService(db_session)
    candles = service.get_candles(
        symbol="TEST",
        resolution="5m",
        start_date=datetime(2026, 4, 15),  # Day before
        end_date=datetime(2026, 4, 17),  # Day after
    )

    assert len(candles) == 1
    assert candles[0].open == 100.0
