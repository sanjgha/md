"""Unit tests for WatchlistService.get_quotes()."""

from datetime import datetime, date
from decimal import Decimal
from typing import cast

import pytest
from sqlalchemy.orm import Session

from src.api.watchlists.service import WatchlistService
from src.db.models import (
    DailyCandle,
    RealtimeQuote,
    Stock,
    User,
    Watchlist,
    WatchlistSymbol,
)


def _make_user(db: Session, username: str = "testuser") -> User:
    user = User(username=username, password_hash="hash")
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_stock(db: Session, symbol: str) -> Stock:
    stock = Stock(symbol=symbol, name=f"{symbol} Inc")
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


def _make_watchlist(db: Session, user_id: int) -> Watchlist:
    wl = Watchlist(
        user_id=user_id,
        name="Test WL",
        is_auto_generated=False,
        watchlist_mode="static",
    )
    db.add(wl)
    db.commit()
    db.refresh(wl)
    return wl


def _add_symbol(
    db: Session, watchlist_id: int, stock_id: int, priority: int = 0
) -> WatchlistSymbol:
    ws = WatchlistSymbol(watchlist_id=watchlist_id, stock_id=stock_id, priority=priority)
    db.add(ws)
    db.commit()
    return ws


class TestGetQuotesOwnership:
    def test_returns_none_for_wrong_owner(self, db_session: Session):
        user1 = _make_user(db_session, "u1")
        user2 = _make_user(db_session, "u2")
        wl = _make_watchlist(db_session, cast(int, user1.id))

        service = WatchlistService(db_session)
        result = service.get_quotes(cast(int, wl.id), cast(int, user2.id))
        assert result is None

    def test_returns_empty_list_for_empty_watchlist(self, db_session: Session):
        user = _make_user(db_session)
        wl = _make_watchlist(db_session, cast(int, user.id))

        service = WatchlistService(db_session)
        result = service.get_quotes(cast(int, wl.id), cast(int, user.id))
        assert result == []


class TestGetQuotesRealtimePriority:
    def test_realtime_quote_returned_when_present_today(self, db_session: Session):
        user = _make_user(db_session)
        stock = _make_stock(db_session, "AAPL")
        wl = _make_watchlist(db_session, cast(int, user.id))
        _add_symbol(db_session, cast(int, wl.id), cast(int, stock.id))

        rq = RealtimeQuote(
            stock_id=cast(int, stock.id),
            last=Decimal("186.59"),
            change=Decimal("9.31"),
            change_pct=Decimal("5.25"),
            timestamp=datetime.combine(date.today(), datetime.min.time()),
        )
        db_session.add(rq)
        db_session.commit()

        service = WatchlistService(db_session)
        result = service.get_quotes(cast(int, wl.id), cast(int, user.id))

        assert result is not None
        assert len(result) == 1
        assert result[0].symbol == "AAPL"
        assert result[0].last == pytest.approx(186.59)
        assert result[0].change == pytest.approx(9.31)
        assert result[0].change_pct == pytest.approx(5.25)
        assert result[0].source == "realtime"

    def test_old_realtime_quote_falls_back_to_eod(self, db_session: Session):
        user = _make_user(db_session)
        stock = _make_stock(db_session, "GSAT")
        wl = _make_watchlist(db_session, cast(int, user.id))
        _add_symbol(db_session, cast(int, wl.id), cast(int, stock.id))

        from datetime import timedelta

        yesterday = datetime.combine(date.today() - timedelta(days=1), datetime.min.time())
        rq = RealtimeQuote(
            stock_id=cast(int, stock.id),
            last=Decimal("79.00"),
            change=Decimal("-1.00"),
            change_pct=Decimal("-1.25"),
            timestamp=yesterday,
        )
        db_session.add(rq)
        dc1 = DailyCandle(
            stock_id=cast(int, stock.id),
            timestamp=datetime(2026, 4, 15),
            open=Decimal("79.50"),
            high=Decimal("80.00"),
            low=Decimal("79.00"),
            close=Decimal("79.85"),
            volume=10000,
        )
        dc2 = DailyCandle(
            stock_id=cast(int, stock.id),
            timestamp=datetime(2026, 4, 14),
            open=Decimal("79.00"),
            high=Decimal("79.90"),
            low=Decimal("78.80"),
            close=Decimal("79.89"),
            volume=9000,
        )
        db_session.add_all([dc1, dc2])
        db_session.commit()

        service = WatchlistService(db_session)
        result = service.get_quotes(cast(int, wl.id), cast(int, user.id))

        assert result is not None
        assert result[0].source == "eod"
        assert result[0].last == pytest.approx(79.85)


class TestGetQuotesEodFallback:
    def test_eod_change_computed_from_two_candles(self, db_session: Session):
        user = _make_user(db_session)
        stock = _make_stock(db_session, "TSLA")
        wl = _make_watchlist(db_session, cast(int, user.id))
        _add_symbol(db_session, cast(int, wl.id), cast(int, stock.id))

        dc1 = DailyCandle(
            stock_id=cast(int, stock.id),
            timestamp=datetime(2026, 4, 15),
            open=Decimal("200.00"),
            high=Decimal("210.00"),
            low=Decimal("199.00"),
            close=Decimal("205.00"),
            volume=50000,
        )
        dc2 = DailyCandle(
            stock_id=cast(int, stock.id),
            timestamp=datetime(2026, 4, 14),
            open=Decimal("195.00"),
            high=Decimal("201.00"),
            low=Decimal("194.00"),
            close=Decimal("200.00"),
            volume=45000,
        )
        db_session.add_all([dc1, dc2])
        db_session.commit()

        service = WatchlistService(db_session)
        result = service.get_quotes(cast(int, wl.id), cast(int, user.id))

        assert result is not None
        assert result[0].source == "eod"
        assert result[0].last == pytest.approx(205.00)
        assert result[0].change == pytest.approx(5.00)
        assert result[0].change_pct == pytest.approx(2.50)

    def test_eod_change_is_null_with_only_one_candle(self, db_session: Session):
        user = _make_user(db_session)
        stock = _make_stock(db_session, "NEWCO")
        wl = _make_watchlist(db_session, cast(int, user.id))
        _add_symbol(db_session, cast(int, wl.id), cast(int, stock.id))

        dc = DailyCandle(
            stock_id=cast(int, stock.id),
            timestamp=datetime(2026, 4, 15),
            open=Decimal("10.00"),
            high=Decimal("11.00"),
            low=Decimal("9.50"),
            close=Decimal("10.50"),
            volume=1000,
        )
        db_session.add(dc)
        db_session.commit()

        service = WatchlistService(db_session)
        result = service.get_quotes(cast(int, wl.id), cast(int, user.id))

        assert result is not None
        assert result[0].last == pytest.approx(10.50)
        assert result[0].change is None
        assert result[0].change_pct is None

    def test_symbol_with_no_data_excluded(self, db_session: Session):
        user = _make_user(db_session)
        stock = _make_stock(db_session, "GHOST")
        wl = _make_watchlist(db_session, cast(int, user.id))
        _add_symbol(db_session, cast(int, wl.id), cast(int, stock.id))

        service = WatchlistService(db_session)
        result = service.get_quotes(cast(int, wl.id), cast(int, user.id))

        assert result == []

    def test_results_ordered_by_symbol_priority(self, db_session: Session):
        user = _make_user(db_session)
        stock_a = _make_stock(db_session, "AAA")
        stock_b = _make_stock(db_session, "BBB")
        wl = _make_watchlist(db_session, cast(int, user.id))
        _add_symbol(db_session, cast(int, wl.id), cast(int, stock_a.id), priority=1)
        _add_symbol(db_session, cast(int, wl.id), cast(int, stock_b.id), priority=0)

        for stock in [stock_a, stock_b]:
            dc = DailyCandle(
                stock_id=cast(int, stock.id),
                timestamp=datetime(2026, 4, 15),
                open=Decimal("10.00"),
                high=Decimal("11.00"),
                low=Decimal("9.50"),
                close=Decimal("10.50"),
                volume=1000,
            )
            db_session.add(dc)
        db_session.commit()

        service = WatchlistService(db_session)
        result = service.get_quotes(cast(int, wl.id), cast(int, user.id))

        assert result is not None
        assert len(result) == 2
        assert result[0].symbol == "BBB"
        assert result[1].symbol == "AAA"
