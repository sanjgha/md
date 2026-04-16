"""Integration tests for GET /api/watchlists/{id}/quotes."""

from datetime import datetime, date
from decimal import Decimal

from src.db.models import (
    DailyCandle,
    RealtimeQuote,
    Stock,
    Watchlist,
    WatchlistCategory,
    WatchlistSymbol,
)


def _setup_watchlist(db_session, user):
    """Helper: create a watchlist with AAPL (realtime) and GSAT (EOD)."""
    cat = WatchlistCategory(user_id=user.id, name="Test", is_system=False, sort_order=0)
    db_session.add(cat)
    db_session.commit()

    wl = Watchlist(
        user_id=user.id,
        name="My WL",
        category_id=cat.id,
        is_auto_generated=False,
        watchlist_mode="static",
    )
    db_session.add(wl)

    aapl = Stock(symbol="AAPL", name="Apple Inc")
    gsat = Stock(symbol="GSAT", name="Globalstar")
    db_session.add_all([aapl, gsat])
    db_session.commit()

    ws_aapl = WatchlistSymbol(watchlist_id=wl.id, stock_id=aapl.id, priority=0)
    ws_gsat = WatchlistSymbol(watchlist_id=wl.id, stock_id=gsat.id, priority=1)
    db_session.add_all([ws_aapl, ws_gsat])

    # Realtime for AAPL (today)
    rq = RealtimeQuote(
        stock_id=aapl.id,
        last=Decimal("186.59"),
        change=Decimal("9.31"),
        change_pct=Decimal("5.25"),
        timestamp=datetime.combine(date.today(), datetime.min.time()),
    )
    # EOD for GSAT
    dc1 = DailyCandle(
        stock_id=gsat.id,
        timestamp=datetime(2026, 4, 15),
        open=Decimal("79.50"),
        high=Decimal("80.00"),
        low=Decimal("79.00"),
        close=Decimal("79.85"),
        volume=10000,
    )
    dc2 = DailyCandle(
        stock_id=gsat.id,
        timestamp=datetime(2026, 4, 14),
        open=Decimal("79.00"),
        high=Decimal("79.90"),
        low=Decimal("78.80"),
        close=Decimal("79.89"),
        volume=9000,
    )
    db_session.add_all([rq, dc1, dc2])
    db_session.commit()

    return wl, aapl, gsat


def test_quotes_happy_path(authenticated_client, seeded_user, db_session):
    """GET /api/watchlists/{id}/quotes returns quotes for all symbols."""
    user, _ = seeded_user
    wl, aapl, gsat = _setup_watchlist(db_session, user)

    resp = authenticated_client.get(f"/api/watchlists/{wl.id}/quotes")
    assert resp.status_code == 200
    data = resp.json()

    assert len(data) == 2

    aapl_row = next(r for r in data if r["symbol"] == "AAPL")
    assert aapl_row["last"] == 186.59
    assert aapl_row["change"] == 9.31
    assert aapl_row["source"] == "realtime"

    gsat_row = next(r for r in data if r["symbol"] == "GSAT")
    assert gsat_row["source"] == "eod"
    assert gsat_row["last"] == 79.85


def test_quotes_requires_auth(api_client, db_session):
    """GET /api/watchlists/{id}/quotes returns 401 without session."""
    resp = api_client.get("/api/watchlists/999/quotes")
    assert resp.status_code == 401


def test_quotes_404_wrong_owner(authenticated_client, seeded_user, db_session):
    """GET /api/watchlists/{id}/quotes returns 404 for another user's watchlist."""
    from src.db.models import User
    from src.api.auth import hash_password

    other = User(id=2, username="other", password_hash=hash_password("pw"))
    db_session.add(other)
    db_session.commit()

    wl = Watchlist(
        user_id=other.id,
        name="Their WL",
        is_auto_generated=False,
        watchlist_mode="static",
    )
    db_session.add(wl)
    db_session.commit()

    resp = authenticated_client.get(f"/api/watchlists/{wl.id}/quotes")
    assert resp.status_code == 404


def test_quotes_empty_watchlist(authenticated_client, seeded_user, db_session):
    """GET /api/watchlists/{id}/quotes returns [] for a watchlist with no symbols."""
    user, _ = seeded_user
    wl = Watchlist(
        user_id=user.id,
        name="Empty",
        is_auto_generated=False,
        watchlist_mode="static",
    )
    db_session.add(wl)
    db_session.commit()

    resp = authenticated_client.get(f"/api/watchlists/{wl.id}/quotes")
    assert resp.status_code == 200
    assert resp.json() == []
