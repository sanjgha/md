"""Moving average indicators: SMA, EMA, WMA."""

import numpy as np
from typing import List
from src.data_provider.base import Candle
from src.scanner.indicators.base import Indicator


class SMA(Indicator):
    """Simple Moving Average."""

    def compute(self, candles: List[Candle], period: int = 50, **kwargs) -> np.ndarray:
        """Compute SMA of closing prices."""
        closes = np.array([c.close for c in candles], dtype=float)
        if len(closes) < period:
            return np.array([])
        weights = np.ones(period) / period
        return np.convolve(closes, weights, mode="valid")


class EMA(Indicator):
    """Exponential Moving Average — seeded with SMA of first `period` values."""

    def compute(self, candles: List[Candle], period: int = 50, **kwargs) -> np.ndarray:
        """Compute EMA seeded from SMA; returns len - period + 1 values."""
        closes = np.array([c.close for c in candles], dtype=float)
        if len(closes) < period:
            return np.array([])

        alpha = 2 / (period + 1)
        ema_values = [np.mean(closes[:period])]
        for close in closes[period:]:
            ema_values.append(alpha * close + (1 - alpha) * ema_values[-1])

        return np.array(ema_values)


class WMA(Indicator):
    """Weighted Moving Average."""

    def compute(self, candles: List[Candle], period: int = 50, **kwargs) -> np.ndarray:
        """Compute WMA with linearly increasing weights."""
        closes = np.array([c.close for c in candles], dtype=float)
        if len(closes) < period:
            return np.array([])
        weights = np.arange(1, period + 1)
        return np.convolve(closes, weights[::-1], mode="valid") / weights.sum()
