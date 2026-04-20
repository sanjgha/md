from datetime import date


def test_compute_and_store_ivr(db_session):
    from tests.options_agent.conftest import synthetic_bars_rising_volatility
    from src.options_agent.ivr import compute_and_store_ivr
    from src.db.models import IVRSnapshot, Stock

    # IVRSnapshot.symbol is a FK to stocks.symbol — seed the stock first
    stock = Stock(symbol="AAPL", name="Apple Inc")
    db_session.add(stock)
    db_session.commit()

    bars = synthetic_bars_rising_volatility()
    result = compute_and_store_ivr(db_session, "AAPL", bars, as_of=date(2026, 4, 18))

    stored = (
        db_session.query(IVRSnapshot).filter_by(symbol="AAPL", calculation_basis="hv_proxy").one()
    )
    assert stored.ivr == result.ivr


def test_compute_and_store_ivr_upserts(db_session):
    from tests.options_agent.conftest import synthetic_bars_rising_volatility
    from src.options_agent.ivr import compute_and_store_ivr
    from src.db.models import IVRSnapshot, Stock

    stock = Stock(symbol="AAPL", name="Apple Inc")
    db_session.add(stock)
    db_session.commit()

    bars = synthetic_bars_rising_volatility()
    compute_and_store_ivr(db_session, "AAPL", bars, as_of=date(2026, 4, 18))
    compute_and_store_ivr(db_session, "AAPL", bars, as_of=date(2026, 4, 18))
    count = db_session.query(IVRSnapshot).filter_by(symbol="AAPL").count()
    assert count == 1
