"""Synthetic bar fixture helpers for options_agent tests."""

import numpy as np
import pandas as pd
import pytest
from datetime import date, timedelta
from sqlalchemy.orm import Session


@pytest.fixture
def client(db_session: Session):
    """Test client with DB dependency overridden to testcontainers session."""
    from fastapi.testclient import TestClient
    from src.api.main import create_app
    from src.api.deps import get_db

    app = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass  # cleanup handled by db_session fixture

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


def _make_bars(closes: list[float]) -> pd.DataFrame:
    n = len(closes)
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(n)]
    return pd.DataFrame({"close": closes, "date": dates})


def synthetic_bars_rising_volatility(n: int = 300) -> pd.DataFrame:
    """Closes that produce increasing realised volatility over time.

    Uses linearly-increasing per-bar volatility in the last 48 bars so that
    the final rolling-HV value is guaranteed to be the maximum in the lookback.
    """
    rng = np.random.default_rng(42)
    # First 252 bars: low vol (0.5% daily)
    low_vol = np.cumprod(1 + rng.normal(0, 0.005, 252)) * 100
    # Last 48 bars: vol scales linearly from 2% → 8% ensuring last HV is max
    vols = np.linspace(0.02, 0.08, 48)
    returns = rng.normal(0, 1, 48) * vols
    high_vol = np.cumprod(1 + returns) * low_vol[-1]
    closes = np.concatenate([low_vol, high_vol]).tolist()
    return _make_bars(closes)


def synthetic_bars_falling_volatility(n: int = 300) -> pd.DataFrame:
    """Closes that produce decreasing realised volatility over time.

    Uses very-low per-bar volatility in the last 48 bars so that
    the final rolling-HV value is guaranteed to be near the minimum.
    """
    rng = np.random.default_rng(7)
    # First 252 bars: high vol (2%–4% daily)
    vols_high = np.linspace(0.04, 0.02, 252)
    returns_high = rng.normal(0, 1, 252) * vols_high
    high_vol = np.cumprod(1 + returns_high) * 100
    # Last 48 bars: very low vol (0.1% daily)
    returns_low = rng.normal(0, 1, 48) * 0.001
    low_vol = np.cumprod(1 + returns_low) * high_vol[-1]
    closes = np.concatenate([high_vol, low_vol]).tolist()
    return _make_bars(closes)


def synthetic_bars_flat(n: int = 300) -> pd.DataFrame:
    """Flat price bars for volatility edge case testing."""
    closes = [100.0] * n
    return _make_bars(closes)
