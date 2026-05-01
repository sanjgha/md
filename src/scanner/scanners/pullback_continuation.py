"""Pullback continuation scanner: trend + geometry + exhaustion + trigger confluence."""

import logging
from typing import List

import numpy as np

from src.scanner.base import Scanner, ScanResult
from src.scanner.context import ScanContext

logger = logging.getLogger(__name__)


class PullbackContinuationScanner(Scanner):
    """Bidirectional pullback continuation: trend + geometry + exhaustion + trigger."""

    timeframe = "daily"
    description = "Bidirectional pullback continuation: trend + geometry + exhaustion + trigger"

    MIN_CANDLES = 80
    PRICE_MIN = 20.0
    AVG_DOLLAR_VOL_MIN = 50_000_000.0
    ATR_PCT_MIN = 1.5

    SWING_MIN_BARS_AGO = 3
    SWING_MAX_BARS_AGO = 15
    RETRACE_MIN = 0.38
    RETRACE_MAX = 0.78
    EXHAUSTION_WINDOW = 3
    EXHAUSTION_REQUIRED = 2
    VOLUME_SURGE_RATIO = 1.2
    SUPPORT_TOUCH_LOOKBACK = 60
    SUPPORT_TOUCH_MIN_HITS = 2
    SUPPORT_ATR_TOLERANCE = 0.5
    LOW_CONVICTION_THRESHOLD = 40

    EXTENSION_MULT = 1.618
    STOP_ATR_MULT = 0.5

    def scan(self, context: ScanContext) -> List[ScanResult]:
        """Return at most one ScanResult per stock; never raise."""
        candles = context.daily_candles
        results: List[ScanResult] = []

        if len(candles) < self.MIN_CANDLES:
            logger.debug(f"Insufficient candles: {len(candles)} < {self.MIN_CANDLES}")
            return results

        try:
            atr_arr = context.get_indicator("atr", period=14)
            if len(atr_arr) < 1:
                return results

            close = float(candles[-1].close)
            if close < self.PRICE_MIN:
                return results

            avg_dollar_vol = float(np.mean([c.close * c.volume for c in candles[-21:-1]]))
            if avg_dollar_vol < self.AVG_DOLLAR_VOL_MIN:
                return results

            atr_val = float(atr_arr[-1])
            if not np.isfinite(atr_val) or atr_val == 0:
                return results
            atr_pct = atr_val / close * 100
            if atr_pct < self.ATR_PCT_MIN:
                return results

            # Subsequent rules (trend / geometry / exhaustion / trigger) added in later tasks.
            return results
        except Exception:
            logger.exception(f"PullbackContinuationScanner failed for {context.symbol}")
            return results
