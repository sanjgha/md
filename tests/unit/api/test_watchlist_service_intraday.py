"""Tests for watchlist service intraday data fetching."""

from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session
from typing import cast

from src.api.watchlists.service import WatchlistService
from src.db.models import (
    DailyCandle,
    IntradayCandle,
    RealtimeQuote,
    Stock,
    User,
    WatchlistCategory,
    WatchlistSymbol,
)


class TestGetQuotesIntraday:
    """Test get_quotes with intraday data."""

    def test_get_quotes_includes_intraday_data(self, db_session: Session):
        """Test that get_quotes includes intraday data points for sparkline."""
        # Create user
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        # Create category
        category = WatchlistCategory(
            user_id=cast(int, user.id),
            name="Test Category",
            icon="🧪",
            is_system=False,
            sort_order=1,
        )
        db_session.add(category)
        db_session.commit()

        # Create watchlist
        service = WatchlistService(db_session)
        watchlist = service.create_watchlist(
            user_id=cast(int, user.id),
            name="Test Watchlist",
            category_id=cast(int, category.id),
        )

        # Create stock
        stock = Stock(symbol="AAPL", name="Apple Inc")
        db_session.add(stock)
        db_session.commit()

        # Create watchlist symbol
        ws = WatchlistSymbol(
            watchlist_id=cast(int, watchlist.id),
            stock_id=stock.id,
            priority=0,
        )
        db_session.add(ws)
        db_session.commit()

        # Create intraday candles for today (for low/high calculation and sparkline)
        today = date.today()
        for i in range(6):
            candle = IntradayCandle(
                stock_id=stock.id,
                resolution="1h",
                timestamp=datetime.combine(today, datetime.min.time()).replace(hour=9, minute=30)
                + timedelta(hours=i),  # hourly from 9:30
                open=Decimal("180.00"),
                high=Decimal("182.00"),
                low=Decimal("179.00"),
                close=Decimal(str(180.50 + i * 0.5)),  # 180.50, 181.00, 181.50, etc.
                volume=1000000,
            )
            db_session.add(candle)

        # Create a realtime quote (triggers intraday lookup)
        rt_quote = RealtimeQuote(
            stock_id=stock.id,
            last=Decimal("183.00"),
            change=Decimal("9.31"),
            change_pct=Decimal("5.01"),
            timestamp=datetime.now(),
        )
        db_session.add(rt_quote)
        db_session.commit()

        # Get quotes
        result = service.get_quotes(cast(int, watchlist.id), cast(int, user.id))

        # Verify results
        assert result is not None
        assert len(result) == 1
        quote = result[0]
        assert quote.symbol == "AAPL"
        assert quote.last == 183.00
        # Low/high should come from intraday data min/max
        assert quote.low == 180.50
        assert quote.high == 183.00
        assert len(quote.intraday) == 6
        # Verify first intraday point (IntradayPoint is a Pydantic model)
        assert quote.intraday[0].close == 180.50

    def test_get_quotes_eod_fallback_no_intraday(self, db_session: Session):
        """Test that EOD quotes have empty intraday array."""
        # Create user
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        # Create watchlist
        service = WatchlistService(db_session)
        watchlist = service.create_watchlist(
            user_id=cast(int, user.id),
            name="Test Watchlist",
        )

        # Create stock
        stock = Stock(symbol="AAPL", name="Apple Inc")
        db_session.add(stock)
        db_session.commit()

        # Create watchlist symbol
        ws = WatchlistSymbol(
            watchlist_id=cast(int, watchlist.id),
            stock_id=stock.id,
            priority=0,
        )
        db_session.add(ws)
        db_session.commit()

        # Create daily candles (no intraday, no realtime)
        today = date.today()
        yesterday = today.replace(day=today.day - 1)
        candle1 = DailyCandle(
            stock_id=stock.id,
            timestamp=datetime.combine(today, datetime.min.time()),
            open=Decimal("180.00"),
            high=Decimal("188.50"),
            low=Decimal("178.20"),
            close=Decimal("186.59"),
            volume=10000000,
        )
        candle2 = DailyCandle(
            stock_id=stock.id,
            timestamp=datetime.combine(yesterday, datetime.min.time()),
            open=Decimal("175.00"),
            high=Decimal("180.00"),
            low=Decimal("174.00"),
            close=Decimal("177.28"),
            volume=10000000,
        )
        db_session.add_all([candle1, candle2])
        db_session.commit()

        # Get quotes
        result = service.get_quotes(cast(int, watchlist.id), cast(int, user.id))

        # Verify results - EOD data with low/high from daily candle
        assert result is not None
        assert len(result) == 1
        assert result[0].source == "eod"
        assert result[0].last == 186.59
        assert result[0].low == 178.20
        assert result[0].high == 188.50
        assert result[0].intraday == []
