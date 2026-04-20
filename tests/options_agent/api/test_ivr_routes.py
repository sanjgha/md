import pytest
from datetime import date


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
