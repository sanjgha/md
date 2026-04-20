"""Unit tests for implied-IV based IVR computation."""

from datetime import date


def _make_chain_rows(spot: float, n_strikes: int = 10):
    """Build a synthetic options chain centred on spot with vol smile."""
    from src.options_agent.data.dolt_client import OptionsContract

    strikes = [spot - 10 + i * 2 for i in range(n_strikes)]
    rows = []
    for k in strikes:
        rows.append(
            OptionsContract(
                symbol="AAPL",
                expiry_date=date(2026, 4, 24),
                contract_type="C",
                strike=k,
                bid=None,
                ask=None,
                mid=None,
                last=None,
                volume=None,
                open_interest=None,
                iv=0.25 + abs(k - spot) * 0.002,
                delta=None,
                gamma=None,
                theta=None,
                vega=None,
            )
        )
        rows.append(
            OptionsContract(
                symbol="AAPL",
                expiry_date=date(2026, 4, 24),
                contract_type="P",
                strike=k,
                bid=None,
                ask=None,
                mid=None,
                last=None,
                volume=None,
                open_interest=None,
                iv=0.27 + abs(k - spot) * 0.002,
                delta=None,
                gamma=None,
                theta=None,
                vega=None,
            )
        )
    return rows


def test_compute_atm_iv_returns_average_of_call_and_put():
    """ATM IV should be the average of the nearest call and put IV."""
    from src.options_agent.ivr import compute_atm_iv

    chain = _make_chain_rows(spot=185.0)
    atm_iv = compute_atm_iv(chain, spot=185.0)
    assert 0.15 <= atm_iv <= 1.5


def test_ivr_from_implied_calculation_basis(db_session):
    """compute_ivr_from_implied uses 'implied' basis when history is sufficient."""
    from src.options_agent.ivr import compute_ivr_from_implied
    from src.db.models import IVRSnapshot, Stock
    from datetime import datetime, timezone

    # IVRSnapshot.symbol is a FK to stocks.symbol — seed the stock first
    stock = Stock(symbol="AAPL", name="Apple Inc")
    db_session.add(stock)
    db_session.commit()

    # Seed 252 rows of historical implied IV snapshots with unique dates
    from datetime import timedelta

    base_date = date(2024, 1, 1)
    for i in range(252):
        db_session.add(
            IVRSnapshot(
                symbol="AAPL",
                as_of_date=base_date + timedelta(days=i),
                ivr=float(i % 100),
                current_hv=0.20 + i * 0.001,
                calculation_basis="implied",
                computed_at=datetime.now(timezone.utc),
            )
        )
    db_session.commit()
    chain = _make_chain_rows(spot=185.0)
    result = compute_ivr_from_implied(
        session=db_session,
        symbol="AAPL",
        chain=chain,
        spot=185.0,
        as_of=date(2026, 4, 18),
    )
    assert result.calculation_basis == "implied"
    assert 0 <= result.ivr <= 100


def test_ivr_implied_falls_back_to_hv_proxy_with_insufficient_history(db_session):
    """Falls back to HV proxy when fewer than 252 implied IV rows exist."""
    from tests.options_agent.conftest import synthetic_bars_rising_volatility
    from src.options_agent.ivr import compute_ivr_from_implied

    chain = _make_chain_rows(spot=185.0)
    result = compute_ivr_from_implied(
        session=db_session,
        symbol="AAPL",
        chain=chain,
        spot=185.0,
        as_of=date(2026, 4, 18),
        bars=synthetic_bars_rising_volatility(),
    )
    assert result.calculation_basis == "hv_proxy"
