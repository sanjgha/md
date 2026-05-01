"""Momentum indicators: RSI and MACD."""

import numpy as np
from typing import List
from src.data_provider.base import Candle
from src.scanner.indicators.base import Indicator


class RSI(Indicator):
    """Relative Strength Index — first value seeded from initial average gain/loss."""

    def compute(self, candles: List[Candle], period: int = 14, **kwargs) -> np.ndarray:
        """Compute RSI with properly seeded first value."""
        closes = np.array([c.close for c in candles], dtype=float)
        if len(closes) < period + 1:
            return np.array([])

        deltas = np.diff(closes)
        gains = np.maximum(deltas, 0)
        losses = np.abs(np.minimum(deltas, 0))

        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])

        rsi_values = []
        if avg_gain == 0 and avg_loss == 0:
            rsi_values.append(50.0)
        elif avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rsi_values.append(100 - (100 / (1 + avg_gain / avg_loss)))

        for i in range(period, len(deltas)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            if avg_gain == 0 and avg_loss == 0:
                rsi_values.append(50.0)
            elif avg_loss == 0:
                rsi_values.append(100.0)
            else:
                rsi_values.append(100 - (100 / (1 + avg_gain / avg_loss)))

        return np.array(rsi_values)


class MACD(Indicator):
    """MACD (Moving Average Convergence Divergence)."""

    def compute(
        self,
        candles: List[Candle],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
        **kwargs,
    ) -> np.ndarray:
        """Compute MACD line (fast EMA - slow EMA)."""
        closes = np.array([c.close for c in candles], dtype=float)
        fast_ema = self._ema(closes, fast_period)
        slow_ema = self._ema(closes, slow_period)
        if len(fast_ema) == 0 or len(slow_ema) == 0:
            return np.array([])
        min_len = min(len(fast_ema), len(slow_ema))
        return fast_ema[-min_len:] - slow_ema[-min_len:]

    @staticmethod
    def _ema(values: np.ndarray, period: int) -> np.ndarray:
        """Compute EMA of a numpy array."""
        if len(values) < period:
            return np.array([])
        alpha = 2 / (period + 1)
        ema = [np.mean(values[:period])]
        for v in values[period:]:
            ema.append(alpha * v + (1 - alpha) * ema[-1])
        return np.array(ema)


def rsi_divergence(
    prices: np.ndarray,
    rsi: np.ndarray,
    prior_pivot: int,
    current_pivot: int,
) -> tuple[bool, bool]:
    """Detect classical bullish/bearish RSI divergence between two pivots.

    Bullish: price[current] < price[prior] AND rsi[current] > rsi[prior].
    Bearish: price[current] > price[prior] AND rsi[current] < rsi[prior].
    Both indices must be in-bounds; returns (False, False) otherwise.
    """
    if prior_pivot < 0 or current_pivot < 0:
        return (False, False)
    if prior_pivot >= len(prices) or current_pivot >= len(prices):
        return (False, False)
    if prior_pivot >= len(rsi) or current_pivot >= len(rsi):
        return (False, False)

    p_prior, p_curr = float(prices[prior_pivot]), float(prices[current_pivot])
    r_prior, r_curr = float(rsi[prior_pivot]), float(rsi[current_pivot])

    bull = p_curr < p_prior and r_curr > r_prior
    bear = p_curr > p_prior and r_curr < r_prior
    return (bull, bear)
