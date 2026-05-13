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

    def _find_pullback_touch(
        self,
        candles,
        ema_9_arr,
        ema_21_arr,
        atr_arr,
    ) -> dict | None:
        """Scan the last PULLBACK_WINDOW bars (excluding today) for a qualifying pullback touch.

        A touch is valid when the bar's low reached EMA_9 but stayed above
        EMA_21 − EMA21_BUFFER_ATR × ATR.  Returns a dict with keys
        {touch_offset, touch_low, touch_ema_9, touch_ema_21}, or None if no
        touch is found.  Today (offset -1) is excluded; the touch must be a
        prior bar, not the entry bar.
        """
        if (
            len(ema_9_arr) < self.PULLBACK_WINDOW + 1
            or len(ema_21_arr) < self.PULLBACK_WINDOW + 1
            or len(atr_arr) < self.PULLBACK_WINDOW + 1
        ):
            return None

        most_recent_touch: dict | None = None
        # Scan from oldest (-PULLBACK_WINDOW) to newest (-2) so we end with the most recent touch.
        for k in range(self.PULLBACK_WINDOW, 1, -1):
            bar = candles[-k]
            e9 = float(ema_9_arr[-k])
            e21 = float(ema_21_arr[-k])
            atr = float(atr_arr[-k])
            if not (np.isfinite(e9) and np.isfinite(e21) and np.isfinite(atr) and atr > 0):
                continue
            if bar.low <= e9 and bar.low >= e21 - self.EMA21_BUFFER_ATR * atr:
                most_recent_touch = {
                    "touch_offset": -k,
                    "touch_low": float(bar.low),
                    "touch_ema_9": e9,
                    "touch_ema_21": e21,
                }
        return most_recent_touch

    def _build_result(
        self,
        context: ScanContext,
        candles,
        close: float,
        atr_val: float,
        atr_pct: float,
        ema_9_arr,
        ema_21_arr,
        ema_50_arr,
        ema_50_slope_10: float,
        rsi_today: float,
        rs: dict,
        touch: dict,
    ) -> ScanResult:
        """Build a ScanResult with full metadata for an emitted signal."""
        rs_line = rs["rs_line"]
        rs_21_ago = float(rs_line[-1 - self.RS_SLOPE_LOOKBACK])
        rs_slope_pct = (rs["rs_today"] - rs_21_ago) / rs_21_ago * 100.0 if rs_21_ago != 0 else 0.0
        metadata = {
            "close": round(close, 4),
            "atr_14": round(atr_val, 4),
            "atr_pct": round(atr_pct, 4),
            "ema_9": round(float(ema_9_arr[-1]), 4),
            "ema_21": round(float(ema_21_arr[-1]), 4),
            "ema_50": round(float(ema_50_arr[-1]), 4),
            "ema_50_slope_10": round(ema_50_slope_10, 6),
            "rsi_14": round(rsi_today, 2),
            "rs_today": round(rs["rs_today"], 4),
            "rs_sma_today": round(rs["rs_sma_today"], 4),
            "mansfield_rs": round(rs["mansfield"], 4),
            "rs_line_21_bars_ago": round(rs_21_ago, 4),
            "rs_slope_pct": round(rs_slope_pct, 4),
            "benchmark_symbol": self.BENCHMARK_SYMBOL,
            "pullback_touch_idx_offset": int(touch["touch_offset"]),
            "pullback_touch_low": round(touch["touch_low"], 4),
            "pullback_touch_ema_9": round(touch["touch_ema_9"], 4),
            "pullback_touch_ema_21": round(touch["touch_ema_21"], 4),
            "signal_date": candles[-1].timestamp.strftime("%Y-%m-%d"),
        }
        return ScanResult(
            stock_id=context.stock_id,
            scanner_name="ema_pullback_rs",
            metadata=metadata,
        )

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

            touch = self._find_pullback_touch(candles, ema_9_arr, ema_21_arr, atr_arr)
            if touch is None:
                return []
            if close <= float(ema_9_arr[-1]):
                return []

            rsi_arr = context.get_indicator("rsi", period=self.RSI_PERIOD)
            if len(rsi_arr) < 1 or not np.isfinite(rsi_arr[-1]):
                return []
            rsi_today = float(rsi_arr[-1])
            if not (self.RSI_MIN <= rsi_today <= self.RSI_MAX):
                return []

            return [
                self._build_result(
                    context,
                    candles,
                    close,
                    atr_val,
                    atr_pct,
                    ema_9_arr,
                    ema_21_arr,
                    ema_50_arr,
                    ema_50_slope_10,
                    rsi_today,
                    rs,
                    touch,
                )
            ]
        except Exception:
            logger.exception("EmaPullbackRsScanner failed for %s", context.symbol)
            return []
