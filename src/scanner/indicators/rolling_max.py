"""Rolling maximum indicator for detecting price highs over N periods."""

import numpy as np
from typing import List
from src.data_provider.base import Candle
from src.scanner.indicators.base import Indicator


class RollingMax(Indicator):
    """Rolling maximum of close prices over N periods."""

    def compute(self, candles: List[Candle], period: int = 126, **kwargs) -> np.ndarray:
        """Compute rolling maximum of closing prices.

        Args:
            candles: List of Candle objects
            period: Number of periods for rolling window (default 126 for ~6 months)

        Returns:
            numpy array where each value is the max close in the window.
            Length is len(candles) - period + 1.
            Returns empty array if len(candles) < period.
        """
        closes = np.array([c.close for c in candles], dtype=float)

        if len(closes) < period:
            return np.array([])

        # Use pandas-like rolling max: for each window of size `period`, take max
        # Result has length: len(closes) - period + 1
        result = np.zeros(len(closes) - period + 1)

        for i in range(len(result)):
            window = closes[i : i + period]
            result[i] = np.max(window)

        return result
