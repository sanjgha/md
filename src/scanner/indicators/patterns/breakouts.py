"""Breakout detection indicator."""

import numpy as np
from typing import List
from src.data_provider.base import Candle
from src.scanner.indicators.base import Indicator


class BreakoutDetector(Indicator):
    """Returns 1.0=breakout above resistance, -1.0=breakdown below support, 0=none."""

    def compute(self, candles: List[Candle], lookback: int = 20, **kwargs) -> np.ndarray:
        """Detect price breakouts above resistance or below support."""
        closes = np.array([c.close for c in candles], dtype=float)
        highs = np.array([c.high for c in candles], dtype=float)
        lows = np.array([c.low for c in candles], dtype=float)

        if len(closes) < lookback + 1:
            return np.array([])

        n = len(closes) - lookback
        signals = np.zeros(n)

        for i in range(n):
            prior_high = np.max(highs[i : i + lookback])
            prior_low = np.min(lows[i : i + lookback])
            current_close = closes[i + lookback]

            if current_close > prior_high:
                signals[i] = 1.0
            elif current_close < prior_low:
                signals[i] = -1.0

        return signals
