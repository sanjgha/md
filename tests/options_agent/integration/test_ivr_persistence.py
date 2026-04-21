import pytest
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


def test_ivr_compute_with_sufficient_history(db_session):
    """273 candles → compute_and_store_ivr succeeds and row persists."""
    from src.options_agent.ivr import compute_and_store_ivr
    from src.db.models import IVRSnapshot, Stock
    import pandas as pd
    import numpy as np
    from datetime import timedelta

    stock = Stock(symbol="NVDA", name="NVIDIA Corp")
    db_session.add(stock)
    db_session.commit()

    # Generate 273 daily candles with realistic close prices
    base = date(2024, 1, 2)
    np.random.seed(42)
    closes = 100.0 * np.cumprod(1 + np.random.normal(0.001, 0.02, 273))
    bars = pd.DataFrame(
        {
            "date": [base + timedelta(days=i) for i in range(273)],
            "close": closes,
        }
    )
    as_of = date(2024, 10, 31)
    result = compute_and_store_ivr(db_session, "NVDA", bars, as_of=as_of)

    stored = db_session.query(IVRSnapshot).filter_by(symbol="NVDA").one()
    assert stored.as_of_date is not None
    assert float(stored.ivr) == pytest.approx(result.ivr, rel=1e-4)
