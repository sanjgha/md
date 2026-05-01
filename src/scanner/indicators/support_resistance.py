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


class SwingPoints(Indicator):
    """Fractal-style swing high/low detector.

    A bar i is a swing high if high[i] > max(high[i-2..i-1]) AND high[i] > max(high[i+1..i+2]).
    Mirror condition for swing lows on lows[].

    Returns a dict {'highs': np.ndarray of shape (n,2), 'lows': np.ndarray of shape (n,2)}
    where each row is (bar_index, price). Indices and prices are floats.
    Only swings within the last `lookback` bars (default 60) of the input are returned.
    """

    def compute(  # type: ignore[override]
        self, candles: List[Candle], lookback: int = 60, **kwargs
    ) -> dict[str, np.ndarray]:
        """Detect fractal swing highs and lows within the last `lookback` bars."""
        highs = np.array([c.high for c in candles], dtype=float)
        lows = np.array([c.low for c in candles], dtype=float)
        n = len(candles)
        if n < 5:
            return {"highs": np.empty((0, 2)), "lows": np.empty((0, 2))}

        start = max(2, n - lookback)
        end = n - 2  # need 2 bars after for fractal

        swing_highs: list[tuple[int, float]] = []
        swing_lows: list[tuple[int, float]] = []
        for i in range(start, end):
            if (
                highs[i] > highs[i - 1]
                and highs[i] > highs[i - 2]
                and highs[i] > highs[i + 1]
                and highs[i] > highs[i + 2]
            ):
                swing_highs.append((i, highs[i]))
            if (
                lows[i] < lows[i - 1]
                and lows[i] < lows[i - 2]
                and lows[i] < lows[i + 1]
                and lows[i] < lows[i + 2]
            ):
                swing_lows.append((i, lows[i]))

        highs_arr = np.array(swing_highs, dtype=float) if swing_highs else np.empty((0, 2))
        lows_arr = np.array(swing_lows, dtype=float) if swing_lows else np.empty((0, 2))
        return {"highs": highs_arr, "lows": lows_arr}
