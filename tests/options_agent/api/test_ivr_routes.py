import pytest
from datetime import date, timezone


@pytest.fixture
def seed_ivr(db_session):
    from src.db.models import IVRSnapshot, Stock
    from datetime import datetime

    stock = Stock(symbol="AAPL", name="Apple Inc")
    db_session.add(stock)
    db_session.commit()

    snap = IVRSnapshot(
        symbol="AAPL",
        as_of_date=date(2026, 4, 18),
        ivr=34.5,
        current_value=0.2312,
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
    from src.db.models import RegimeSnapshot, Stock
    from datetime import datetime

    stock = Stock(symbol="AAPL", name="Apple Inc")
    db_session.add(stock)
    db_session.commit()

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


def test_get_regime_bulk(client, db_session):
    """Test get_regime_bulk route returns regime snapshots for multiple symbols."""
    from src.db.models import RegimeSnapshot, Stock
    from datetime import datetime

    stock1 = Stock(symbol="AAPL", name="Apple Inc")
    stock2 = Stock(symbol="NVDA", name="NVIDIA Corp")
    db_session.add(stock1)
    db_session.add(stock2)
    db_session.commit()

    snap1 = RegimeSnapshot(
        symbol="AAPL",
        as_of_date=date(2026, 4, 18),
        regime="trending",
        direction="bullish",
        adx=32.5,
        atr_pct=0.018,
        spy_trend_20d=0.00234,
        computed_at=datetime.now(timezone.utc),
    )
    snap2 = RegimeSnapshot(
        symbol="NVDA",
        as_of_date=date(2026, 4, 18),
        regime="ranging",
        direction=None,
        adx=18.2,
        atr_pct=0.012,
        spy_trend_20d=0.001,
        computed_at=datetime.now(timezone.utc),
    )
    db_session.add(snap1)
    db_session.add(snap2)
    db_session.commit()

    resp = client.get("/api/options/regime?symbols=AAPL,NVDA")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 2

    # Find AAPL and NVDA in response (order not guaranteed)
    aapl = next((item for item in body if item["symbol"] == "AAPL"), None)
    nvda = next((item for item in body if item["symbol"] == "NVDA"), None)

    assert aapl is not None
    assert nvda is not None

    assert aapl["regime"] == "trending"
    assert aapl["direction"] == "bullish"
    assert aapl["adx"] == 32.5

    assert nvda["regime"] == "ranging"
    assert nvda["direction"] is None
    assert nvda["adx"] == 18.2


def test_get_regime_bulk_partial_data(client, db_session):
    """Test get_regime_bulk returns only symbols with data."""
    from src.db.models import RegimeSnapshot, Stock
    from datetime import datetime

    stock = Stock(symbol="AAPL", name="Apple Inc")
    db_session.add(stock)
    db_session.commit()

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

    # Request both AAPL (has data) and NVDA (no data)
    resp = client.get("/api/options/regime?symbols=AAPL,NVDA")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["symbol"] == "AAPL"
