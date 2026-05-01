"""Pullback continuation scanner: trend + geometry + exhaustion + trigger confluence."""

import logging
from typing import List, cast

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

    def _trend_ok_long(
        self,
        ema_9_arr: np.ndarray,
        ema_21_arr: np.ndarray,
        ema_50_arr: np.ndarray,
        candles: list,
        h_idx: int,
        ema_50_slope_10: float,
    ) -> bool:
        n = len(candles)
        offset = -(n - h_idx)
        ema_9_h, ema_21_h, ema_50_h = self._stack_at(ema_9_arr, ema_21_arr, ema_50_arr, offset)
        close_h = float(candles[h_idx].close)
        if not (ema_9_h > ema_21_h > ema_50_h):
            return False
        if not (close_h > ema_21_h):
            return False
        if ema_50_slope_10 <= 0:
            return False
        return True

    def _trend_ok_short(
        self,
        ema_9_arr: np.ndarray,
        ema_21_arr: np.ndarray,
        ema_50_arr: np.ndarray,
        candles: list,
        h_idx: int,
        l_idx: int,
        ema_50_slope_10: float,
    ) -> bool:
        n = len(candles)
        h_off = -(n - h_idx)
        l_off = -(n - l_idx)
        ema_9_h, ema_21_h, ema_50_h = self._stack_at(ema_9_arr, ema_21_arr, ema_50_arr, h_off)
        ema_21_l = float(ema_21_arr[l_off])
        close_h = float(candles[h_idx].close)
        close_l = float(candles[l_idx].close)
        if not (ema_9_h > ema_21_h > ema_50_h):
            return False
        if not (close_h > ema_21_h):
            return False
        if not (close_l < ema_21_l):
            return False
        if ema_50_slope_10 > 0:  # spec: flat-to-negative for short
            return False
        return True

    @staticmethod
    def _macd_histogram(macd_line: np.ndarray, signal_period: int = 9) -> np.ndarray:
        """Return MACD histogram (macd_line − EMA(macd_line, signal_period)).

        Note: the EMA seed drops the first ``signal_period - 1`` bars, so the
        returned array is shorter than ``macd_line``. Consumers MUST index from
        the tail (e.g. ``hist[-1]``); index 0 of the histogram does NOT line up
        with index 0 of ``macd_line``.
        """
        if len(macd_line) < signal_period:
            return np.array([])
        alpha = 2 / (signal_period + 1)
        sig = [float(np.mean(macd_line[:signal_period]))]
        for v in macd_line[signal_period:]:
            sig.append(alpha * float(v) + (1 - alpha) * sig[-1])
        sig_arr = np.array(sig)
        # macd_line and sig_arr are aligned at the tail.
        min_len = min(len(macd_line), len(sig_arr))
        return macd_line[-min_len:] - sig_arr[-min_len:]

    def _support_levels(self, candles: list, atr_val: float) -> list[float]:
        """Return prices that have been tested ≥2× in the last 60 bars within ±0.5×ATR.

        Cluster lows over the lookback window; a cluster of ≥SUPPORT_TOUCH_MIN_HITS lows
        within SUPPORT_ATR_TOLERANCE×ATR of each other becomes a level (its mean).
        """
        lookback = self.SUPPORT_TOUCH_LOOKBACK
        tail = candles[-lookback:] if len(candles) >= lookback else candles
        lows = sorted(c.low for c in tail)
        if not lows or atr_val <= 0:
            return []
        tol = self.SUPPORT_ATR_TOLERANCE * atr_val

        levels: list[float] = []
        cluster: list[float] = [lows[0]]
        for v in lows[1:]:
            # Anchor span to the cluster's first member so chained values can't
            # silently grow beyond the tolerance bound.
            if v - cluster[0] <= tol:
                cluster.append(v)
            else:
                if len(cluster) >= self.SUPPORT_TOUCH_MIN_HITS:
                    levels.append(float(np.mean(cluster)))
                cluster = [v]
        if len(cluster) >= self.SUPPORT_TOUCH_MIN_HITS:
            levels.append(float(np.mean(cluster)))
        return levels

    def _resistance_levels(self, candles: list, atr_val: float) -> list[float]:
        lookback = self.SUPPORT_TOUCH_LOOKBACK
        tail = candles[-lookback:] if len(candles) >= lookback else candles
        highs = sorted((c.high for c in tail), reverse=True)
        if not highs or atr_val <= 0:
            return []
        tol = self.SUPPORT_ATR_TOLERANCE * atr_val
        levels: list[float] = []
        cluster: list[float] = [highs[0]]
        for v in highs[1:]:
            # Anchor span to the cluster's first member so chained values can't
            # silently grow beyond the tolerance bound.
            if cluster[0] - v <= tol:
                cluster.append(v)
            else:
                if len(cluster) >= self.SUPPORT_TOUCH_MIN_HITS:
                    levels.append(float(np.mean(cluster)))
                cluster = [v]
        if len(cluster) >= self.SUPPORT_TOUCH_MIN_HITS:
            levels.append(float(np.mean(cluster)))
        return levels

    def _exhaustion_long(
        self,
        candles: list,
        atr_val: float,
        rsi_arr: np.ndarray,
        macd_hist: np.ndarray,
        prior_pullback_low_idx: int,
        prior_pullback_low: float,
    ) -> tuple[int, list[str]]:
        """Return (count, reasons) — count of distinct exhaustion criteria fired in last 3 bars."""
        from src.scanner.indicators.momentum import rsi_divergence

        n = len(candles)
        levels = self._support_levels(candles, atr_val)
        tol = self.SUPPORT_ATR_TOLERANCE * atr_val
        avg_vol_20 = float(np.mean([c.volume for c in candles[-21:-1]])) if n >= 21 else 0.0

        reasons: set[str] = set()
        closes = np.array([c.close for c in candles], dtype=float)

        for k in range(self.EXHAUSTION_WINDOW):
            bar_idx = n - 1 - k
            bar = candles[bar_idx]

            # support_hold
            for lvl in levels:
                if abs(bar.low - lvl) <= tol and bar.close > lvl:
                    reasons.add("support_hold")
                    break

            # rsi_div — current pivot is bar_idx, prior is prior_pullback_low_idx
            if len(rsi_arr) > 0 and bar_idx < n and prior_pullback_low_idx < n:
                rsi_offset_today = -(n - bar_idx)
                rsi_offset_prior = -(n - prior_pullback_low_idx)
                if abs(rsi_offset_today) <= len(rsi_arr) and abs(rsi_offset_prior) <= len(rsi_arr):
                    bull, _ = rsi_divergence(
                        closes,
                        np.concatenate([np.full(n - len(rsi_arr), np.nan), rsi_arr]),
                        prior_pivot=prior_pullback_low_idx,
                        current_pivot=bar_idx,
                    )
                    if bull and bar.low < prior_pullback_low:
                        reasons.add("rsi_div")

            # volume_surge
            if avg_vol_20 > 0 and bar.volume > self.VOLUME_SURGE_RATIO * avg_vol_20:
                reasons.add("volume_surge")

            # macd_cross — histogram crossed from negative to ≥0 on this bar
            if len(macd_hist) >= 2:
                hist_today_off = -(n - bar_idx)
                hist_prev_off = hist_today_off - 1
                if abs(hist_today_off) <= len(macd_hist) and abs(hist_prev_off) <= len(macd_hist):
                    h_today = float(macd_hist[hist_today_off])
                    h_prev = float(macd_hist[hist_prev_off])
                    if h_prev < 0 and h_today >= 0:
                        reasons.add("macd_cross")

        return len(reasons), sorted(reasons)

    def _exhaustion_short(
        self,
        candles: list,
        atr_val: float,
        rsi_arr: np.ndarray,
        macd_hist: np.ndarray,
        prior_bounce_high_idx: int,
        prior_bounce_high: float,
    ) -> tuple[int, list[str]]:
        from src.scanner.indicators.momentum import rsi_divergence

        n = len(candles)
        levels = self._resistance_levels(candles, atr_val)
        tol = self.SUPPORT_ATR_TOLERANCE * atr_val
        avg_vol_20 = float(np.mean([c.volume for c in candles[-21:-1]])) if n >= 21 else 0.0

        reasons: set[str] = set()
        closes = np.array([c.close for c in candles], dtype=float)

        for k in range(self.EXHAUSTION_WINDOW):
            bar_idx = n - 1 - k
            bar = candles[bar_idx]

            # resistance_fail
            for lvl in levels:
                if abs(bar.high - lvl) <= tol and bar.close < lvl:
                    reasons.add("resistance_fail")
                    break

            # rsi_div — bearish
            if len(rsi_arr) > 0 and prior_bounce_high_idx < n:
                rsi_offset_today = -(n - bar_idx)
                rsi_offset_prior = -(n - prior_bounce_high_idx)
                if abs(rsi_offset_today) <= len(rsi_arr) and abs(rsi_offset_prior) <= len(rsi_arr):
                    _, bear = rsi_divergence(
                        closes,
                        np.concatenate([np.full(n - len(rsi_arr), np.nan), rsi_arr]),
                        prior_pivot=prior_bounce_high_idx,
                        current_pivot=bar_idx,
                    )
                    if bear and bar.high > prior_bounce_high:
                        reasons.add("rsi_div")

            # volume_surge
            if avg_vol_20 > 0 and bar.volume > self.VOLUME_SURGE_RATIO * avg_vol_20:
                reasons.add("volume_surge")

            # macd_cross — from ≥0 to < 0
            if len(macd_hist) >= 2:
                hist_today_off = -(n - bar_idx)
                hist_prev_off = hist_today_off - 1
                if abs(hist_today_off) <= len(macd_hist) and abs(hist_prev_off) <= len(macd_hist):
                    h_today = float(macd_hist[hist_today_off])
                    h_prev = float(macd_hist[hist_prev_off])
                    if h_prev >= 0 and h_today < 0:
                        reasons.add("macd_cross")

        return len(reasons), sorted(reasons)

    def _score(
        self,
        *,
        direction: str,
        exhaustion_count: int,
        retrace_pct: float,
        volume_ratio: float,
        ema_9: float,
        ema_50: float,
        atr_val: float,
        close: float,
        candles: list,
    ) -> int:
        """Weighted conviction score, 0-100, clamped."""
        # Exhaustion (max 30)
        ex_score = {2: 15.0, 3: 22.0, 4: 30.0}.get(exhaustion_count, 0.0)

        # Retracement quality (max 25); peak between 0.5 and 0.618; linear ramp/decline.
        if 0.5 <= retrace_pct <= 0.618:
            retrace_score = 25.0
        elif self.RETRACE_MIN <= retrace_pct < 0.5:
            retrace_score = 25.0 * (retrace_pct - self.RETRACE_MIN) / (0.5 - self.RETRACE_MIN)
        elif 0.618 < retrace_pct <= self.RETRACE_MAX:
            retrace_score = 25.0 * (self.RETRACE_MAX - retrace_pct) / (self.RETRACE_MAX - 0.618)
        else:
            retrace_score = 0.0

        # Volume (max 20): 1.0 → 0; 2.0+ → 20.
        vol_score = max(0.0, min(20.0, (volume_ratio - 1.0) / 1.0 * 20.0))

        # Trend slope (max 15): 0% → 0; 5%+ → 15.
        slope_pct = abs(ema_9 - ema_50) / ema_50 * 100 if ema_50 != 0 else 0.0
        slope_score = min(15.0, slope_pct / 5.0 * 15.0)

        # Distance to nearest support/resistance (max 10) in ATR units.
        if atr_val <= 0:
            distance_score = 0.0
        else:
            if direction == "long":
                levels = self._support_levels(candles, atr_val)
                below = [lvl for lvl in levels if lvl <= close]
                nearest = max(below) if below else None
            else:
                levels = self._resistance_levels(candles, atr_val)
                above = [lvl for lvl in levels if lvl >= close]
                nearest = min(above) if above else None
            if nearest is None:
                distance_score = 0.0
            else:
                distance_atr = abs(close - nearest) / atr_val
                distance_score = max(0.0, min(10.0, 10.0 - distance_atr * 5.0))

        total = ex_score + retrace_score + vol_score + slope_score + distance_score
        return int(min(100, max(0, round(total))))

    def _build_result(
        self,
        context: ScanContext,
        candles: list,
        atr_val: float,
        atr_pct: float,
        close: float,
        direction: str,
        sig: dict,
    ) -> ScanResult:
        geo = sig["geo"]
        # Round inputs first so stop/target stay self-consistent with the
        # metadata fields they're derived from (avoids rounding-order drift).
        atr_r = round(atr_val, 4)
        close_r = round(close, 4)
        if direction == "long":
            anchor_price = geo["H_high"]
            leg_size = round(geo["up_leg"], 4)
            pullback_extreme = round(geo["pullback_low"], 4)
            stop_level = pullback_extreme - self.STOP_ATR_MULT * atr_r
            target_level = close_r + self.EXTENSION_MULT * leg_size
            anchor_idx = len(candles) - 1 - geo["H_idx"]
        else:
            anchor_price = geo["L_low"]
            leg_size = round(geo["down_leg"], 4)
            pullback_extreme = round(geo["bounce_high"], 4)
            stop_level = pullback_extreme + self.STOP_ATR_MULT * atr_r
            target_level = close_r - self.EXTENSION_MULT * leg_size
            anchor_idx = len(candles) - 1 - geo["L_idx"]

        risk = abs(close_r - stop_level)
        risk_reward = abs(target_level - close_r) / risk if risk > 0 else 0.0

        avg_vol_20 = float(np.mean([c.volume for c in candles[-21:-1]]))
        volume_ratio = float(candles[-1].volume) / avg_vol_20 if avg_vol_20 > 0 else 0.0

        conviction_score = self._score(
            direction=direction,
            exhaustion_count=sig["exhaustion_count"],
            retrace_pct=geo["retrace_pct"],
            volume_ratio=volume_ratio,
            ema_9=sig["ema_9_today"],
            ema_50=sig["ema_50_today"],
            atr_val=atr_val,
            close=close,
            candles=candles,
        )

        metadata = {
            "direction": direction,
            "conviction_score": conviction_score,
            "low_conviction": conviction_score < self.LOW_CONVICTION_THRESHOLD,
            "close": close_r,
            "atr": atr_r,
            "atr_pct": round(atr_pct, 4),
            "ema_9": round(sig["ema_9_today"], 4),
            "ema_21": round(sig["ema_21_today"], 4),
            "ema_50": round(sig["ema_50_today"], 4),
            "ema_50_slope_10": round(sig["ema_50_slope_10"], 6),
            "rsi_14": round(sig["rsi_today"], 2),
            "macd_histogram": round(sig["macd_hist_today"], 6),
            "swing_anchor_idx": anchor_idx,
            "swing_anchor_price": round(anchor_price, 4),
            "leg_size": leg_size,
            "pullback_extreme": pullback_extreme,
            "retrace_pct": round(geo["retrace_pct"], 4),
            "exhaustion_count": sig["exhaustion_count"],
            "exhaustion_reasons": sig["exhaustion_reasons"],
            "volume_ratio": round(volume_ratio, 4),
            "stop_level": round(stop_level, 4),
            "target_level": round(target_level, 4),
            "risk_reward": round(risk_reward, 4),
            "signal_date": candles[-1].timestamp.strftime("%Y-%m-%d"),
        }
        return ScanResult(
            stock_id=context.stock_id,
            scanner_name="pullback_continuation",
            metadata=metadata,
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

            # --- Indicators (long path) ---
            ema_9_arr = context.get_indicator("ema", period=9)
            ema_21_arr = context.get_indicator("ema", period=21)
            ema_50_arr = context.get_indicator("ema", period=50)
            rsi_arr = context.get_indicator("rsi", period=14)
            macd_arr = context.get_indicator(
                "macd", fast_period=12, slow_period=26, signal_period=9
            )
            # SwingPoints returns dict[str, np.ndarray]; cache typing is ndarray-only.
            swings = cast(dict, context.get_indicator("swing_points", lookback=60))

            if (
                len(ema_9_arr) < 1
                or len(ema_21_arr) < 1
                or len(ema_50_arr) < 11
                or len(rsi_arr) < 4
                or len(macd_arr) < 10
            ):
                return results
            for arr in (ema_9_arr, ema_21_arr, ema_50_arr, rsi_arr, macd_arr):
                if not np.all(np.isfinite(arr[-12:])):
                    return results

            ema_50_today = float(ema_50_arr[-1])
            ema_50_10_back = float(ema_50_arr[-11])
            ema_50_slope_10 = (
                (ema_50_today - ema_50_10_back) / ema_50_10_back if ema_50_10_back != 0 else 0.0
            )
            macd_hist = self._macd_histogram(macd_arr, signal_period=9)

            # --- Long branch ---
            long_geo = self._find_long_geometry(candles, swings)
            long_signal = None
            if long_geo and self._trend_ok_long(
                ema_9_arr, ema_21_arr, ema_50_arr, candles, long_geo["H_idx"], ema_50_slope_10
            ):
                # Trigger today
                ema_9_today = float(ema_9_arr[-1])
                three_bar_high = max(c.high for c in candles[-4:-1])
                if close > ema_9_today and close > three_bar_high:
                    count, reasons = self._exhaustion_long(
                        candles,
                        atr_val,
                        rsi_arr,
                        macd_hist,
                        prior_pullback_low_idx=long_geo["pullback_low_idx"],
                        prior_pullback_low=long_geo["pullback_low"],
                    )
                    if count >= self.EXHAUSTION_REQUIRED:
                        long_signal = {
                            "geo": long_geo,
                            "exhaustion_count": count,
                            "exhaustion_reasons": reasons,
                            "ema_9_today": ema_9_today,
                            "ema_21_today": float(ema_21_arr[-1]),
                            "ema_50_today": ema_50_today,
                            "ema_50_slope_10": ema_50_slope_10,
                            "rsi_today": float(rsi_arr[-1]),
                            "macd_hist_today": float(macd_hist[-1]),
                        }

            if long_signal is not None:
                results.append(
                    self._build_result(
                        context, candles, atr_val, atr_pct, close, "long", long_signal
                    )
                )
                return results

            # --- Short branch ---
            short_geo = self._find_short_geometry(candles, swings)
            short_signal = None
            if short_geo and self._trend_ok_short(
                ema_9_arr,
                ema_21_arr,
                ema_50_arr,
                candles,
                short_geo["H_idx"],
                short_geo["L_idx"],
                ema_50_slope_10,
            ):
                ema_21_today = float(ema_21_arr[-1])
                three_bar_low = min(c.low for c in candles[-4:-1])
                if close < ema_21_today and close < three_bar_low:
                    count, reasons = self._exhaustion_short(
                        candles,
                        atr_val,
                        rsi_arr,
                        macd_hist,
                        prior_bounce_high_idx=short_geo["bounce_high_idx"],
                        prior_bounce_high=short_geo["bounce_high"],
                    )
                    if count >= self.EXHAUSTION_REQUIRED:
                        short_signal = {
                            "geo": short_geo,
                            "exhaustion_count": count,
                            "exhaustion_reasons": reasons,
                            "ema_9_today": float(ema_9_arr[-1]),
                            "ema_21_today": ema_21_today,
                            "ema_50_today": ema_50_today,
                            "ema_50_slope_10": ema_50_slope_10,
                            "rsi_today": float(rsi_arr[-1]),
                            "macd_hist_today": float(macd_hist[-1]),
                        }

            if short_signal is not None:
                results.append(
                    self._build_result(
                        context, candles, atr_val, atr_pct, close, "short", short_signal
                    )
                )
                return results

            return results
        except Exception:
            logger.exception(f"PullbackContinuationScanner failed for {context.symbol}")
            return results
