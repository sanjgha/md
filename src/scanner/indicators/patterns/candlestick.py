"""Candlestick pattern detection indicator."""

import numpy as np
from typing import List
from src.data_provider.base import Candle
from src.scanner.indicators.base import Indicator


class CandlestickPatterns(Indicator):
    """Pattern codes: 1=bullish_engulf, -1=bearish_engulf, 2=doji, 0=none."""

    def compute(self, candles: List[Candle], **kwargs) -> np.ndarray:
        """Detect candlestick patterns: doji and engulfing."""
        if len(candles) < 2:
            return np.array([])

        signals = np.zeros(len(candles))

        for i in range(1, len(candles)):
            prev, curr = candles[i - 1], candles[i]
            curr_range = curr.high - curr.low
            curr_body = abs(curr.close - curr.open)

            if curr_range > 0 and curr_body / curr_range < 0.1:
                signals[i] = 2  # Doji
            elif (
                prev.close < prev.open
                and curr.close > curr.open
                and curr.open <= prev.close
                and curr.close >= prev.open
            ):
                signals[i] = 1  # Bullish engulfing
            elif (
                prev.close > prev.open
                and curr.close < curr.open
                and curr.open >= prev.close
                and curr.close <= prev.open
            ):
                signals[i] = -1  # Bearish engulfing

        return signals
