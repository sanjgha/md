"""Mansfield Relative Strength helper — pure function, not registered in IndicatorCache.

The cache keys on a single candle series; a two-series indicator (stock vs. benchmark)
doesn't fit that model cleanly. Callers pass benchmark candles in directly.
"""

from typing import List, Optional

import numpy as np

from src.data_provider.base import Candle


def compute_mansfield_rs(
    stock_candles: List[Candle],
    benchmark_candles: List[Candle],
    sma_period: int = 260,
    slope_lookback: int = 21,
) -> Optional[dict]:
    """Align stock + benchmark by timestamp, compute Dorsey ratio, Mansfield, slope.

    Returns dict with keys (rs_line, rs_sma, rs_today, rs_sma_today, mansfield,
    rs_slope_ok), or None if fewer than `sma_period` aligned bars or if any
    relevant tail value is NaN/inf.
    """
    if not stock_candles or not benchmark_candles:
        return None

    stock_by_ts = {c.timestamp: c.close for c in stock_candles}
    bench_by_ts = {c.timestamp: c.close for c in benchmark_candles}
    aligned_ts = sorted(set(stock_by_ts.keys()) & set(bench_by_ts.keys()))

    if len(aligned_ts) < sma_period:
        return None

    stock_arr = np.array([stock_by_ts[t] for t in aligned_ts], dtype=float)
    bench_arr = np.array([bench_by_ts[t] for t in aligned_ts], dtype=float)

    if not (np.all(np.isfinite(stock_arr)) and np.all(np.isfinite(bench_arr))):
        return None
    if np.any(bench_arr == 0):
        return None

    rs_line = (stock_arr / bench_arr) * 100.0

    weights = np.ones(sma_period) / sma_period
    rs_sma = np.convolve(rs_line, weights, mode="valid")

    if not np.all(np.isfinite(rs_sma[-1:])) or not np.all(
        np.isfinite(rs_line[-(slope_lookback + 1) :])
    ):
        return None
    if rs_sma[-1] == 0:
        return None

    rs_today = float(rs_line[-1])
    rs_sma_today = float(rs_sma[-1])
    mansfield = (rs_today / rs_sma_today - 1.0) * 100.0
    rs_slope_ok = bool(rs_line[-1] > rs_line[-1 - slope_lookback])

    return {
        "rs_line": rs_line,
        "rs_sma": rs_sma,
        "rs_today": rs_today,
        "rs_sma_today": rs_sma_today,
        "mansfield": float(mansfield),
        "rs_slope_ok": rs_slope_ok,
    }
