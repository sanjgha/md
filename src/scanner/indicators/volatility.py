"""Volatility indicators: BollingerBands and ATR."""

import numpy as np
from typing import List
from src.data_provider.base import Candle
from src.scanner.indicators.base import Indicator


class BollingerBands(Indicator):
    """Bollinger Bands: returns (upper, middle, lower) as shape (n, 3) array."""

    def compute(
        self, candles: List[Candle], period: int = 20, std_dev: float = 2.0, **kwargs
    ) -> np.ndarray:
        """Compute Bollinger Bands; returns array of shape (n, 3)."""
        closes = np.array([c.close for c in candles], dtype=float)
        if len(closes) < period:
            return np.array([]).reshape(0, 3)

        n = len(closes) - period + 1
        upper, middle, lower = np.zeros(n), np.zeros(n), np.zeros(n)

        for i in range(n):
            window = closes[i : i + period]
            mean = np.mean(window)
            std = np.std(window, ddof=0)
            middle[i] = mean
            upper[i] = mean + std_dev * std
            lower[i] = mean - std_dev * std

        return np.column_stack([upper, middle, lower])


class ATR(Indicator):
    """Average True Range."""

    def compute(self, candles: List[Candle], period: int = 14, **kwargs) -> np.ndarray:
        """Compute ATR using true range rolling mean."""
        if len(candles) < period + 1:
            return np.array([])

        highs = np.array([c.high for c in candles], dtype=float)
        lows = np.array([c.low for c in candles], dtype=float)
        closes = np.array([c.close for c in candles], dtype=float)

        tr = np.maximum(
            highs[1:] - lows[1:],
            np.maximum(
                np.abs(highs[1:] - closes[:-1]),
                np.abs(lows[1:] - closes[:-1]),
            ),
        )

        n = len(tr) - period + 1
        return np.array([np.mean(tr[i : i + period]) for i in range(n)])
