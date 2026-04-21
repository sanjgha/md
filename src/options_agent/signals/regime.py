"""Market regime detection: trending / ranging / transitional."""

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal

import numpy as np
import pandas as pd

from src.options_agent.ivr import InsufficientHistoryError


@dataclass
class RegimeResult:
    """Market regime classification with supporting metrics."""

    regime: Literal["trending", "ranging", "transitional"]
    direction: Literal["bullish", "bearish", "neutral", "unclear"] | None
    adx: float
    atr_pct: float
    spy_trend_20d: float


def _adx(df: pd.DataFrame, period: int = 14) -> float:
    if len(df) < 2 * period:
        raise InsufficientHistoryError(
            f"Need at least {2 * period} bars for ADX calculation, got {len(df)}"
        )

    high, low, close = df["high"].values, df["low"].values, df["close"].values
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1])),
    )
    dm_plus = np.where(
        (high[1:] - high[:-1]) > (low[:-1] - low[1:]),
        np.maximum(high[1:] - high[:-1], 0),
        0,
    )
    dm_minus = np.where(
        (low[:-1] - low[1:]) > (high[1:] - high[:-1]),
        np.maximum(low[:-1] - low[1:], 0),
        0,
    )

    def _wilder_ema(x: np.ndarray) -> np.ndarray:
        return pd.Series(x).ewm(alpha=1.0 / period, adjust=False).mean().values

    atr_s = _wilder_ema(tr)
    safe_atr = np.where(atr_s == 0, 1, atr_s)
    di_plus = 100 * _wilder_ema(dm_plus) / safe_atr
    di_minus = 100 * _wilder_ema(dm_minus) / safe_atr
    denom = np.where(di_plus + di_minus == 0, 1, di_plus + di_minus)
    dx = 100 * abs(di_plus - di_minus) / denom
    adx_series = _wilder_ema(dx)
    return float(adx_series[-1])


def _atr_pct(df: pd.DataFrame, period: int = 14) -> float:
    high, low, close = df["high"].values, df["low"].values, df["close"].values
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1])),
    )
    atr = tr[-period:].mean()
    return float(atr / close[-1])


def _spy_trend_slope(spy: pd.DataFrame, window: int = 20) -> float:
    closes = spy["close"].values[-window:]
    x = np.arange(window, dtype=float)
    slope = np.polyfit(x, closes, 1)[0]
    return float(slope / closes[0])


def detect_regime(bars: pd.DataFrame, spy_bars: pd.DataFrame) -> RegimeResult:
    """Classify market regime as trending, ranging, or transitional."""
    adx = _adx(bars)
    atr_pct = _atr_pct(bars)
    spy_trend = _spy_trend_slope(spy_bars)

    if adx < 20 and atr_pct < 0.015:
        return RegimeResult(
            regime="ranging",
            direction="neutral",
            adx=adx,
            atr_pct=atr_pct,
            spy_trend_20d=spy_trend,
        )

    if adx > 25 and atr_pct <= 0.03:
        direction: Literal["bullish", "bearish", "neutral", "unclear"]
        if spy_trend > 0.001:
            direction = "bullish"
        elif spy_trend < -0.001:
            direction = "bearish"
        else:
            ema20 = bars["close"].ewm(span=20).mean().iloc[-1]
            direction = "bullish" if bars["close"].iloc[-1] > ema20 else "bearish"
        return RegimeResult(
            regime="trending",
            direction=direction,
            adx=adx,
            atr_pct=atr_pct,
            spy_trend_20d=spy_trend,
        )

    return RegimeResult(
        regime="transitional",
        direction="unclear",
        adx=adx,
        atr_pct=atr_pct,
        spy_trend_20d=spy_trend,
    )


def compute_and_store_regime(
    session,
    symbol: str,
    bars: pd.DataFrame,
    spy_bars: pd.DataFrame,
    as_of: date,
) -> RegimeResult:
    """Compute regime and upsert into regime_snapshots."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from src.db.models import RegimeSnapshot

    result = detect_regime(bars, spy_bars)
    now = datetime.now(timezone.utc)
    stmt = (
        pg_insert(RegimeSnapshot)
        .values(
            symbol=symbol,
            as_of_date=as_of,
            regime=result.regime,
            direction=result.direction,
            adx=result.adx,
            atr_pct=result.atr_pct,
            spy_trend_20d=result.spy_trend_20d,
            computed_at=now,
        )
        .on_conflict_do_update(
            constraint="uq_regime_symbol_date",
            set_={
                "regime": result.regime,
                "direction": result.direction,
                "adx": result.adx,
                "atr_pct": result.atr_pct,
                "spy_trend_20d": result.spy_trend_20d,
                "computed_at": now,
            },
        )
    )
    session.execute(stmt)
    session.commit()
    return result
