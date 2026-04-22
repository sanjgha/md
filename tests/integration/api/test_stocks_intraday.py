"""Integration tests for intraday candles with realtime quote endpoint."""

from datetime import date, datetime

from decimal import Decimal

from src.db.models import IntradayCandle, RealtimeQuote, Stock


def test_get_intraday_candles_with_realtime(api_client, db_session):
    """Should return today's intraday candles merged with latest realtime quote."""
    # Create test data
    stock = Stock(symbol="AAPL", name="Apple Inc")
    db_session.add(stock)
    db_session.flush()

    # Create intraday candles for today
    today = date.today()
    candles = [
        IntradayCandle(
            stock_id=stock.id,
            resolution="1h",
            timestamp=datetime(today.year, today.month, today.day, 9, 30),
            open=Decimal("180.20"),
            high=Decimal("182.40"),
            low=Decimal("179.80"),
            close=Decimal("181.50"),
            volume=1000000,
        ),
        IntradayCandle(
            stock_id=stock.id,
            resolution="1h",
            timestamp=datetime(today.year, today.month, today.day, 10, 30),
            open=Decimal("181.50"),
            high=Decimal("184.20"),
            low=Decimal("181.00"),
            close=Decimal("183.75"),
            volume=1200000,
        ),
    ]
    for candle in candles:
        db_session.add(candle)

    # Create realtime quote
    quote = RealtimeQuote(
        stock_id=stock.id,
        last=Decimal("186.59"),
        change=Decimal("6.39"),
        change_pct=Decimal("3.55"),
        timestamp=datetime.now(),
    )
    db_session.add(quote)
    db_session.commit()

    response = api_client.get("/api/stocks/AAPL/candles/intraday?resolution=1h")

    assert response.status_code == 200
    data = response.json()
    assert "intraday" in data
    assert "realtime" in data
    assert len(data["intraday"]) == 2
    assert data["realtime"]["symbol"] == "AAPL"
    assert data["realtime"]["last"] == 186.59
    assert data["realtime"]["change"] == 6.39
    assert data["realtime"]["change_pct"] == 3.55


def test_get_intraday_candles_unknown_symbol_returns_404(api_client):
    """Test that unknown symbol returns 404."""
    response = api_client.get("/api/stocks/UNKNOWN/candles/intraday?resolution=1h")

    assert response.status_code == 404


def test_get_intraday_candles_no_realtime_quote(api_client, db_session):
    """Test that endpoint works when no realtime quote exists."""
    stock = Stock(symbol="AAPL", name="Apple Inc")
    db_session.add(stock)
    db_session.flush()

    today = date.today()
    candle = IntradayCandle(
        stock_id=stock.id,
        resolution="1h",
        timestamp=datetime(today.year, today.month, today.day, 9, 30),
        open=Decimal("180.20"),
        high=Decimal("182.40"),
        low=Decimal("179.80"),
        close=Decimal("181.50"),
        volume=1000000,
    )
    db_session.add(candle)
    db_session.commit()

    response = api_client.get("/api/stocks/AAPL/candles/intraday?resolution=1h")

    assert response.status_code == 200
    data = response.json()
    assert "intraday" in data
    assert "realtime" in data
    assert len(data["intraday"]) == 1
    assert data["realtime"] is None
