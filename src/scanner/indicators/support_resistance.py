"""Support and resistance level detection."""

import numpy as np
from typing import List
from src.data_provider.base import Candle
from src.scanner.indicators.base import Indicator


class SupportResistance(Indicator):
    """Detect support and resistance levels via rolling min/max."""

    def compute(self, candles: List[Candle], lookback: int = 20, **kwargs) -> np.ndarray:
        """Compute midpoint between rolling support and resistance levels."""
        lows = np.array([c.low for c in candles], dtype=float)
        highs = np.array([c.high for c in candles], dtype=float)

        if len(lows) < 1:
            return np.array([])

        support = np.array([np.min(lows[max(0, i - lookback) : i + 1]) for i in range(len(lows))])
        resistance = np.array(
            [np.max(highs[max(0, i - lookback) : i + 1]) for i in range(len(highs))]
        )

        return (support + resistance) / 2
