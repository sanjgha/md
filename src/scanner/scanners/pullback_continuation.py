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

    def _find_long_geometry(
        self,
        candles: list,
        swings: dict,
    ) -> dict | None:
        """Find a long-eligible pullback structure ending today.

        Returns:
            dict with keys H_idx, H_high, L_idx, L_low, up_leg, pullback_low_idx,
                 pullback_low, retrace_pct — or None if no qualifying structure.
        """
        n = len(candles)
        today_idx = n - 1
        highs_arr = swings.get("highs", np.empty((0, 2)))
        lows_arr = swings.get("lows", np.empty((0, 2)))
        if highs_arr.size == 0 or lows_arr.size == 0:
            return None

        sh = [(int(i), float(p)) for i, p in highs_arr]
        sl = [(int(i), float(p)) for i, p in lows_arr]

        candidates = [
            (idx, price)
            for idx, price in sh
            if self.SWING_MIN_BARS_AGO <= (today_idx - idx) <= self.SWING_MAX_BARS_AGO
        ]
        if not candidates:
            return None
        h_idx, h_high = max(candidates, key=lambda t: t[0])

        prior_lows = [(idx, price) for idx, price in sl if idx < h_idx]
        if not prior_lows:
            return None
        l_idx, l_low = max(prior_lows, key=lambda t: t[0])

        up_leg = h_high - l_low
        if up_leg <= 0:
            return None

        pullback_low_idx = h_idx + 1 + int(np.argmin([candles[i].low for i in range(h_idx + 1, n)]))
        pullback_low = float(candles[pullback_low_idx].low)

        retrace_pct = (h_high - pullback_low) / up_leg
        if retrace_pct < self.RETRACE_MIN or retrace_pct > self.RETRACE_MAX:
            return None

        return {
            "H_idx": h_idx,
            "H_high": h_high,
            "L_idx": l_idx,
            "L_low": l_low,
            "up_leg": up_leg,
            "pullback_low_idx": pullback_low_idx,
            "pullback_low": pullback_low,
            "retrace_pct": retrace_pct,
        }

    def _find_short_geometry(
        self,
        candles: list,
        swings: dict,
    ) -> dict | None:
        n = len(candles)
        today_idx = n - 1
        highs_arr = swings.get("highs", np.empty((0, 2)))
        lows_arr = swings.get("lows", np.empty((0, 2)))
        if highs_arr.size == 0 or lows_arr.size == 0:
            return None

        sh = [(int(i), float(p)) for i, p in highs_arr]
        sl = [(int(i), float(p)) for i, p in lows_arr]

        candidates = [
            (idx, price)
            for idx, price in sl
            if self.SWING_MIN_BARS_AGO <= (today_idx - idx) <= self.SWING_MAX_BARS_AGO
        ]
        if not candidates:
            return None
        l_idx, l_low = max(candidates, key=lambda t: t[0])

        prior_highs = [(idx, price) for idx, price in sh if idx < l_idx]
        if not prior_highs:
            return None
        h_idx, h_high = max(prior_highs, key=lambda t: t[0])

        down_leg = h_high - l_low
        if down_leg <= 0:
            return None

        bounce_high_idx = l_idx + 1 + int(np.argmax([candles[i].high for i in range(l_idx + 1, n)]))
        bounce_high = float(candles[bounce_high_idx].high)

        retrace_pct = (bounce_high - l_low) / down_leg
        if retrace_pct < self.RETRACE_MIN or retrace_pct > self.RETRACE_MAX:
            return None

        return {
            "H_idx": h_idx,
            "H_high": h_high,
            "L_idx": l_idx,
            "L_low": l_low,
            "down_leg": down_leg,
            "bounce_high_idx": bounce_high_idx,
            "bounce_high": bounce_high,
            "retrace_pct": retrace_pct,
        }

    def _stack_at(
        self,
        ema_9_arr: np.ndarray,
        ema_21_arr: np.ndarray,
        ema_50_arr: np.ndarray,
        anchor_neg_offset: int,
    ) -> tuple[float, float, float]:
        """Return (ema_9, ema_21, ema_50) at the bar identified by a negative offset.

        All three EMA arrays end at "today"; offset -1 = today, -2 = yesterday, etc.
        """
        return (
            float(ema_9_arr[anchor_neg_offset]),
            float(ema_21_arr[anchor_neg_offset]),
            float(ema_50_arr[anchor_neg_offset]),
        )

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

            ema_9_arr = context.get_indicator("ema", period=9)
            ema_21_arr = context.get_indicator("ema", period=21)
            ema_50_arr = context.get_indicator("ema", period=50)
            if len(ema_9_arr) < 1 or len(ema_21_arr) < 1 or len(ema_50_arr) < 11:
                return results
            for arr in (ema_9_arr, ema_21_arr, ema_50_arr):
                if not np.all(np.isfinite(arr[-12:])):
                    return results

            ema_50_today = float(ema_50_arr[-1])
            ema_50_10_back = float(ema_50_arr[-11])
            ema_50_slope_10 = (  # noqa: F841 — used in Task 14 trend gating
                (ema_50_today - ema_50_10_back) / ema_50_10_back if ema_50_10_back != 0 else 0.0
            )

            swings = context.get_indicator("swing_points", lookback=60)  # noqa: F841 — wired in Task 16

            # Subsequent rules (trend / geometry / exhaustion / trigger) added in later tasks.
            return results
        except Exception:
            logger.exception(f"PullbackContinuationScanner failed for {context.symbol}")
            return results
