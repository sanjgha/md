"""IVR (Implied Volatility Rank) computation using HV as proxy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert


class InsufficientHistoryError(ValueError):
    """Raised when there are not enough bars to compute IVR."""

    pass


@dataclass
class IVRResult:
    """Result of an IVR computation."""

    ivr: float
    current_hv: float
    hv_min: float
    hv_max: float
    calculation_basis: str
    as_of: date


def compute_ivr_from_hv(
    bars: pd.DataFrame,
    window: int = 20,
    lookback: int = 252,
) -> IVRResult:
    """Compute IV Rank using historical volatility as a proxy.

    Args:
        bars: DataFrame with 'close' column, sorted oldest-first.
        window: rolling window for HV computation (trading days).
        lookback: number of HV values to rank against.
    """
    closes = bars["close"].astype(float).values
    if len(closes) < window + lookback:
        raise InsufficientHistoryError(f"Need at least {window + lookback} bars, got {len(closes)}")

    log_returns = np.log(closes[1:] / closes[:-1])
    hv_series = pd.Series(log_returns).rolling(window).std().dropna() * np.sqrt(252)
    hv_values = hv_series.values

    if len(hv_values) < lookback:
        raise InsufficientHistoryError(f"Need at least {lookback} HV values, got {len(hv_values)}")

    history = hv_values[-lookback:]
    current = hv_values[-1]
    hv_min = float(history.min())
    hv_max = float(history.max())

    if hv_max == hv_min:
        ivr = 0.0
    else:
        ivr = float((current - hv_min) / (hv_max - hv_min) * 100)

    as_of_val = bars["date"].iloc[-1] if "date" in bars.columns else date.today()

    return IVRResult(
        ivr=round(ivr, 2),
        current_hv=round(float(current), 4),
        hv_min=round(hv_min, 4),
        hv_max=round(hv_max, 4),
        calculation_basis="hv_proxy",
        as_of=as_of_val,
    )


def compute_and_store_ivr(
    session: Session,
    symbol: str,
    bars: pd.DataFrame,
    as_of: date,
    window: int = 20,
    lookback: int = 252,
) -> IVRResult:
    """Compute IVR from HV proxy and upsert into ivr_snapshots table."""
    from src.db.models import IVRSnapshot

    result = compute_ivr_from_hv(bars, window=window, lookback=lookback)
    stmt = (
        pg_insert(IVRSnapshot)
        .values(
            symbol=symbol,
            as_of_date=as_of,
            ivr=result.ivr,
            current_hv=result.current_hv,
            calculation_basis=result.calculation_basis,
            computed_at=datetime.now(timezone.utc),
        )
        .on_conflict_do_update(
            constraint="uq_ivr_symbol_date_basis",
            set_={
                "ivr": result.ivr,
                "current_hv": result.current_hv,
                "computed_at": datetime.now(timezone.utc),
            },
        )
    )
    session.execute(stmt)
    session.commit()
    return result


def compute_atm_iv(chain: list[Any], spot: float) -> float:
    """Return the average IV of the ATM call and ATM put nearest to spot."""
    calls = [c for c in chain if c.contract_type == "C" and c.iv is not None]
    puts = [c for c in chain if c.contract_type == "P" and c.iv is not None]
    if not calls or not puts:
        raise ValueError("No contracts with IV data.")
    atm_call = min(calls, key=lambda c: abs(c.strike - spot))
    atm_put = min(puts, key=lambda c: abs(c.strike - spot))
    return (atm_call.iv + atm_put.iv) / 2


def compute_ivr_from_implied(
    session: Session,
    symbol: str,
    chain: list[Any],
    spot: float,
    as_of: date,
    lookback: int = 252,
    bars: pd.DataFrame | None = None,
) -> IVRResult:
    """Compute IVR from real implied volatility; falls back to HV proxy if history is insufficient."""
    from src.db.models import IVRSnapshot

    historical = (
        session.query(IVRSnapshot.current_hv)
        .filter_by(symbol=symbol, calculation_basis="implied")
        .order_by(IVRSnapshot.as_of_date.desc())
        .limit(lookback)
        .all()
    )
    if len(historical) < lookback:
        if bars is None:
            raise InsufficientHistoryError(
                f"Only {len(historical)} days of implied IV history; need {lookback}."
            )
        return compute_ivr_from_hv(bars)

    current_iv = compute_atm_iv(chain, spot)
    history = np.array([float(r[0]) for r in reversed(historical)])
    hv_min = float(history.min())
    hv_max = float(history.max())
    ivr = 0.0 if hv_max == hv_min else float((current_iv - hv_min) / (hv_max - hv_min) * 100)

    return IVRResult(
        ivr=round(ivr, 2),
        current_hv=round(current_iv, 4),
        hv_min=round(hv_min, 4),
        hv_max=round(hv_max, 4),
        calculation_basis="implied",
        as_of=as_of,
    )
