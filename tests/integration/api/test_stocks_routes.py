"""Integration tests for stocks API routes."""

from datetime import datetime

from src.db.models import IntradayCandle, Stock


def test_get_candles_5m_happy_path(api_client, db_session):
    """Test successful 5m candle retrieval."""
    # Setup test data
    stock = Stock(symbol="AAPL", name="Apple Inc")
    db_session.add(stock)
    db_session.flush()

    candle = IntradayCandle(
        stock_id=stock.id,
        resolution="5m",
        timestamp=datetime(2026, 4, 16, 9, 30),
        open=180.20,
        high=188.40,
        low=179.80,
        close=186.59,
        volume=52300000,
    )
    db_session.add(candle)
    db_session.commit()

    response = api_client.get(
        "/api/stocks/AAPL/candles?resolution=5m&from=2026-04-16&to=2026-04-17"
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["open"] == 180.20
    assert data[0]["close"] == 186.59


def test_get_candles_unknown_symbol_returns_404(api_client):
    """Test that unknown symbol returns 404."""
    response = api_client.get(
        "/api/stocks/UNKNOWN/candles?resolution=D&from=2026-04-16&to=2026-04-17"
    )

    assert response.status_code == 404


def test_get_candles_invalid_resolution_returns_400(api_client):
    """Test that invalid resolution returns 400."""
    response = api_client.get(
        "/api/stocks/AAPL/candles?resolution=invalid&from=2026-04-16&to=2026-04-17"
    )

    assert response.status_code == 400


def test_get_candles_exceeds_max_range_returns_400(api_client):
    """Test that exceeding max range returns 400."""
    response = api_client.get(
        "/api/stocks/AAPL/candles?resolution=5m&from=2026-04-01&to=2026-04-20"
    )

    assert response.status_code == 400
