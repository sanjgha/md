from datetime import date, timedelta
import numpy as np
import pandas as pd


def make_trending_bars(n=60):
    """Generate bars that will classify as trending (high ADX, moderate ATR)."""
    closes = 100.0 * np.cumprod(1 + np.random.normal(0.003, 0.012, n))
    opens = closes * 0.999
    highs = closes * 1.01
    lows = closes * 0.99
    dates = [date(2025, 1, 2) + timedelta(days=i) for i in range(n)]
    return pd.DataFrame({"date": dates, "open": opens, "high": highs, "low": lows, "close": closes})


def test_compute_and_store_regime_round_trip(db_session):
    """seed bars → compute_and_store_regime → RegimeSnapshot row exists → API would return 200."""
    from src.options_agent.signals.regime import compute_and_store_regime
    from src.db.models import RegimeSnapshot, Stock

    np.random.seed(99)
    stock = Stock(symbol="AAPL", name="Apple Inc")
    db_session.add(stock)
    db_session.commit()

    bars = make_trending_bars(60)
    spy_bars = make_trending_bars(30)
    as_of = date(2025, 3, 15)

    result = compute_and_store_regime(db_session, "AAPL", bars, spy_bars, as_of=as_of)

    stored = db_session.query(RegimeSnapshot).filter_by(symbol="AAPL").one()
    assert stored.regime == result.regime
    assert stored.direction == result.direction
    assert stored.as_of_date is not None


def test_compute_and_store_regime_upserts(db_session):
    """Calling twice for same symbol+date updates, not duplicates."""
    from src.options_agent.signals.regime import compute_and_store_regime
    from src.db.models import RegimeSnapshot, Stock

    np.random.seed(77)
    stock = Stock(symbol="NVDA", name="NVIDIA")
    db_session.add(stock)
    db_session.commit()

    bars = make_trending_bars(60)
    spy_bars = make_trending_bars(30)
    as_of = date(2025, 3, 15)

    compute_and_store_regime(db_session, "NVDA", bars, spy_bars, as_of=as_of)
    compute_and_store_regime(db_session, "NVDA", bars, spy_bars, as_of=as_of)
    count = db_session.query(RegimeSnapshot).filter_by(symbol="NVDA").count()
    assert count == 1
