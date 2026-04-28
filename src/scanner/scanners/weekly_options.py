"""Weekly options setup scanner: squeeze-break confluence for call/put entries."""

import logging
import numpy as np
from typing import List
from src.scanner.base import Scanner, ScanResult
from src.scanner.context import ScanContext

logger = logging.getLogger(__name__)


class WeeklyOptionsScanner(Scanner):
    """Bidirectional weekly-option setup: squeeze + directional break + trend + volume."""

    timeframe = "daily"
    description = "Bidirectional weekly-option setup: squeeze + directional break + trend + volume"

    MIN_CANDLES = 80
    PRICE_MIN = 20.0
    AVG_DOLLAR_VOL_MIN = 50_000_000.0
    ATR_PCT_MIN = 1.5
    SQUEEZE_PCTILE_MAX = 25.0
    VOLUME_RATIO_MIN = 1.5
    RSI_CALL_MAX = 75.0
    RSI_PUT_MIN = 25.0
    ATR_PCT_WEEKLY_THRESHOLD = 2.5

    def scan(self, context: ScanContext) -> List[ScanResult]:
        """Return at most one ScanResult per stock with direction, score, and trade metadata."""
        candles = context.daily_candles
        results: List[ScanResult] = []

        if len(candles) < self.MIN_CANDLES:
            logger.debug(f"Insufficient candles: {len(candles)} < {self.MIN_CANDLES}")
            return results

        try:
            bb = context.get_indicator("bollinger", period=20)
            ema_20_arr = context.get_indicator("ema", period=20)
            ema_50_arr = context.get_indicator("ema", period=50)
            rsi_arr = context.get_indicator("rsi", period=14)
            atr_arr = context.get_indicator("atr", period=14)
            bb_pctile_arr = context.get_indicator("bb_width_pctile", period=20, lookback=60)

            if (
                len(bb) < 2
                or len(ema_20_arr) < 1
                or len(ema_50_arr) < 1
                or len(rsi_arr) < 1
                or len(atr_arr) < 1
                or len(bb_pctile_arr) < 1
            ):
                return results

            close = float(candles[-1].close)
            today_volume = float(candles[-1].volume)

            # --- Universe filters ---
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

            # --- Extract indicator scalars ---
            bb_upper_today = float(bb[-1, 0])
            bb_middle_today = float(bb[-1, 1])
            bb_lower_today = float(bb[-1, 2])
            bb_upper_prev = float(bb[-2, 0])
            bb_lower_prev = float(bb[-2, 2])

            bb_width = (
                (bb_upper_today - bb_lower_today) / bb_middle_today if bb_middle_today != 0 else 0.0
            )
            bb_pctile = float(bb_pctile_arr[-1])
            ema_20 = float(ema_20_arr[-1])
            ema_50 = float(ema_50_arr[-1])
            rsi_val = float(rsi_arr[-1])

            avg_vol_20 = float(np.mean([c.volume for c in candles[-21:-1]]))
            volume_ratio = today_volume / avg_vol_20 if avg_vol_20 > 0 else 0.0

            # Guard NaN/inf in any indicator
            check = [
                bb_upper_today,
                bb_lower_today,
                bb_middle_today,
                bb_upper_prev,
                bb_lower_prev,
                bb_pctile,
                ema_20,
                ema_50,
                rsi_val,
            ]
            if not all(np.isfinite(v) for v in check):
                return results

            # --- Rule 3: Trend alignment → determines direction ---
            is_bull = close > ema_20 and ema_20 > ema_50
            is_bear = close < ema_20 and ema_20 < ema_50
            if not is_bull and not is_bear:
                return results

            # --- Rule 1: Squeeze ---
            if bb_pctile > self.SQUEEZE_PCTILE_MAX:
                return results

            # --- Rule 2: Directional break (BB band or Donchian) ---
            donchian_closes = [c.close for c in candles[-21:-1]]
            donchian_high = max(donchian_closes)
            donchian_low = min(donchian_closes)

            if is_bull:
                bb_break = close > bb_upper_prev
                donchian_break = close > donchian_high
                break_level = bb_upper_prev if bb_break else donchian_high
            else:
                bb_break = close < bb_lower_prev
                donchian_break = close < donchian_low
                break_level = bb_lower_prev if bb_break else donchian_low

            if not bb_break and not donchian_break:
                return results

            # --- Rule 4: Volume ---
            if volume_ratio < self.VOLUME_RATIO_MIN:
                return results

            # --- Rule 5: No overextension ---
            if is_bull and rsi_val >= self.RSI_CALL_MAX:
                return results
            if is_bear and rsi_val <= self.RSI_PUT_MIN:
                return results

            # --- Direction ---
            direction = "call" if is_bull else "put"

            # --- Conviction score ---
            squeeze_score = max(
                0.0, (self.SQUEEZE_PCTILE_MAX - bb_pctile) / self.SQUEEZE_PCTILE_MAX * 30
            )
            vol_score = max(
                0.0,
                (min(volume_ratio, 3.0) - self.VOLUME_RATIO_MIN)
                / (3.0 - self.VOLUME_RATIO_MIN)
                * 25,
            )
            atr_score = min(20.0, atr_pct / 5.0 * 20)
            trend_slope_pct = abs(ema_20 - ema_50) / ema_50 * 100 if ema_50 != 0 else 0.0
            trend_score = min(15.0, trend_slope_pct / 2.0 * 15)
            break_mag = abs(close - break_level) / atr_val if atr_val > 0 else 0.0
            break_score = min(10.0, break_mag / 0.5 * 10)
            conviction_score = int(
                min(100, max(0, squeeze_score + vol_score + atr_score + trend_score + break_score))
            )

            # --- Break type ---
            if bb_break and donchian_break:
                break_type = "both"
            elif bb_break:
                break_type = "bb_band"
            else:
                break_type = "donchian"

            # --- Suggested expiry ---
            suggested_expiry = (
                "weekly" if atr_pct >= self.ATR_PCT_WEEKLY_THRESHOLD else "next_weekly"
            )

            # --- Target and stop ---
            if direction == "call":
                target_1_atr = close + atr_val
                stop_level = close - 0.5 * atr_val
            else:
                target_1_atr = close - atr_val
                stop_level = close + 0.5 * atr_val

            results.append(
                ScanResult(
                    stock_id=context.stock_id,
                    scanner_name="weekly_options",
                    metadata={
                        "direction": direction,
                        "conviction_score": conviction_score,
                        "close": round(close, 4),
                        "atr": round(atr_val, 4),
                        "atr_pct": round(atr_pct, 4),
                        "bb_width": round(bb_width, 6),
                        "bb_width_pctile": round(bb_pctile, 2),
                        "volume_ratio": round(volume_ratio, 4),
                        "ema_20": round(ema_20, 4),
                        "ema_50": round(ema_50, 4),
                        "rsi_14": round(rsi_val, 2),
                        "break_type": break_type,
                        "suggested_expiry": suggested_expiry,
                        "target_1_atr": round(target_1_atr, 4),
                        "stop_level": round(stop_level, 4),
                        "signal_date": candles[-1].timestamp.strftime("%Y-%m-%d"),
                    },
                )
            )

        except Exception:
            logger.exception(f"WeeklyOptionsScanner failed for {context.symbol}")

        return results
