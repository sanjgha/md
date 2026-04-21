import pytest
from datetime import date, datetime, timezone


@pytest.fixture
def seed_ivr(db_session):
    from src.db.models import IVRSnapshot, Stock
    from datetime import datetime, timezone

    stock = Stock(symbol="AAPL", name="Apple Inc")
    db_session.add(stock)
    db_session.commit()

    snap = IVRSnapshot(
        symbol="AAPL",
        as_of_date=date(2026, 4, 18),
        ivr=34.5,
        current_hv=0.2312,
        calculation_basis="hv_proxy",
        computed_at=datetime.now(timezone.utc),
    )
    db_session.add(snap)
    db_session.commit()
    return snap


def test_get_ivr_for_symbol(client, seed_ivr):
    resp = client.get("/api/options/ivr/AAPL")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "AAPL"
    assert 0 <= body["ivr"] <= 100
    assert body["calculation_basis"] in ("hv_proxy", "implied")


def test_get_ivr_unknown_symbol_404(client):
    resp = client.get("/api/options/ivr/ZZZZ")
    assert resp.status_code == 404


def test_get_ivr_bulk(client, seed_ivr):
    resp = client.get("/api/options/ivr?symbols=AAPL")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) == 1


def test_get_regime_for_symbol(client, db_session):
    """Test get_regime route returns regime snapshot for a symbol."""
    from src.db.models import RegimeSnapshot
    from datetime import datetime, timezone

    snap = RegimeSnapshot(
        symbol="AAPL",
        as_of_date=date(2026, 4, 18),
        regime="trending",
        direction="bullish",
        adx=32.5,
        atr_pct=0.018,
        spy_trend_20d=0.00234,
        computed_at=datetime.now(timezone.utc),
    )
    db_session.add(snap)
    db_session.commit()

    resp = client.get("/api/options/regime/AAPL")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "AAPL"
    assert body["regime"] == "trending"
    assert body["direction"] == "bullish"
    assert body["adx"] == 32.5
    assert body["atr_pct"] == 0.018
    assert body["as_of_date"] == "2026-04-18"


def test_get_regime_unknown_symbol_404(client):
    """Test get_regime route returns 404 for unknown symbol."""
    resp = client.get("/api/options/regime/ZZZZ")
    assert resp.status_code == 404


def test_to_date_with_datetime_object(client, db_session):
    """Test _to_date helper converts datetime to date."""
    from src.api.options.routes import _to_date

    # Test with datetime object
    dt = datetime(2026, 4, 18, 14, 30, 45, tzinfo=timezone.utc)
    result = _to_date(dt)
    assert result == date(2026, 4, 18)
    assert isinstance(result, date)

    # Test with date object (passes through)
    d = date(2026, 4, 18)
    result = _to_date(d)
    assert result == d
