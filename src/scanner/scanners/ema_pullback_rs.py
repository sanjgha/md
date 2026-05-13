"""9/21 EMA pullback scanner with Mansfield relative strength vs. benchmark."""

import logging
from typing import List

import numpy as np

from src.scanner.base import Scanner, ScanResult
from src.scanner.context import ScanContext
from src.scanner.indicators.relative_strength import compute_mansfield_rs

logger = logging.getLogger(__name__)


class EmaPullbackRsScanner(Scanner):
    """Long-only daily scanner: trend stack + 9/21 EMA pullback + RSI band + Mansfield RS."""

    timeframe = "daily"
    description = "9/21 EMA pullback with healthy RSI and rising relative strength vs. SPY"

    # Universe / liquidity gates
    MIN_CANDLES = 280
    PRICE_MIN = 20.0
    AVG_DOLLAR_VOL_MIN = 50_000_000.0
    ATR_PCT_MIN = 1.5

    # Relative strength
    BENCHMARK_SYMBOL = "SPY"
    RS_SMA_PERIOD = 260
    RS_SLOPE_LOOKBACK = 21

    # Pullback geometry
    PULLBACK_WINDOW = 5
    EMA21_BUFFER_ATR = 0.25

    # RSI gate
    RSI_PERIOD = 14
    RSI_MIN = 40.0
    RSI_MAX = 70.0

    # ATR for liquidity gate
    ATR_PERIOD = 14

    def _liquidity_ok(self, candles, atr_arr) -> tuple[bool, float, float, float]:
        """Returns (ok, close, atr_val, atr_pct). atr_val=0 / atr_pct=0 on failure."""
        close = float(candles[-1].close)
        if close < self.PRICE_MIN:
            return (False, close, 0.0, 0.0)
        avg_dollar_vol = float(np.mean([c.close * c.volume for c in candles[-21:-1]]))
        if avg_dollar_vol < self.AVG_DOLLAR_VOL_MIN:
            return (False, close, 0.0, 0.0)
        if len(atr_arr) < 1:
            return (False, close, 0.0, 0.0)
        atr_val = float(atr_arr[-1])
        if not np.isfinite(atr_val) or atr_val <= 0:
            return (False, close, 0.0, 0.0)
        atr_pct = atr_val / close * 100.0
        if atr_pct < self.ATR_PCT_MIN:
            return (False, close, atr_val, atr_pct)
        return (True, close, atr_val, atr_pct)

    def _trend_ok(self, ema_9_arr, ema_21_arr, ema_50_arr) -> tuple[bool, float]:
        """Returns (ok, ema_50_slope_10). Slope is fractional change over last 10 bars."""
        if len(ema_9_arr) < 1 or len(ema_21_arr) < 1 or len(ema_50_arr) < 11:
            return (False, 0.0)
        if not (
            np.all(np.isfinite(ema_9_arr[-1:]))
            and np.all(np.isfinite(ema_21_arr[-1:]))
            and np.all(np.isfinite(ema_50_arr[-11:]))
        ):
            return (False, 0.0)
        e9, e21, e50 = float(ema_9_arr[-1]), float(ema_21_arr[-1]), float(ema_50_arr[-1])
        if not (e9 > e21 > e50):
            return (False, 0.0)
        e50_back = float(ema_50_arr[-11])
        if e50_back == 0:
            return (False, 0.0)
        slope = (e50 - e50_back) / e50_back
        if slope <= 0:
            return (False, slope)
        return (True, slope)

    def _rs_ok(self, context: ScanContext) -> dict | None:
        """Returns the Mansfield dict on pass, else None.

        Reject when:
          - compute_mansfield_rs returns None (insufficient aligned bars or NaN/zero inputs)
          - mansfield <= 0 (not durably outperforming benchmark)
          - rs_slope_ok is False (RS line not rising recently)
        """
        rs = compute_mansfield_rs(
            context.daily_candles,
            context.benchmark_candles,
            sma_period=self.RS_SMA_PERIOD,
            slope_lookback=self.RS_SLOPE_LOOKBACK,
        )
        if rs is None:
            return None
        if rs["mansfield"] <= 0:
            return None
        if not rs["rs_slope_ok"]:
            return None
        return rs

    def scan(self, context: ScanContext) -> List[ScanResult]:
        """Return at most one ScanResult per stock; never raises."""
        try:
            candles = context.daily_candles
            if len(candles) < self.MIN_CANDLES:
                return []
            if not context.benchmark_candles:
                return []

            atr_arr = context.get_indicator("atr", period=self.ATR_PERIOD)
            ok, close, atr_val, atr_pct = self._liquidity_ok(candles, atr_arr)
            if not ok:
                return []

            ema_9_arr = context.get_indicator("ema", period=9)
            ema_21_arr = context.get_indicator("ema", period=21)
            ema_50_arr = context.get_indicator("ema", period=50)
            trend_ok, ema_50_slope_10 = self._trend_ok(ema_9_arr, ema_21_arr, ema_50_arr)
            if not trend_ok:
                return []

            rs = self._rs_ok(context)
            if rs is None:
                return []

            # Remaining gates implemented in subsequent tasks.
            return []
        except Exception:
            logger.exception("EmaPullbackRsScanner failed for %s", context.symbol)
            return []
