"""ICT-style Smart Money scanner with FVG + MSS entry detection."""

import logging
from typing import List, Dict, Optional
from src.scanner.base import Scanner, ScanResult
from src.scanner.context import ScanContext
from src.scanner.indicators.patterns.fvg import FractalSwings, FVGDetector

logger = logging.getLogger(__name__)


class SmartMoneyScanner(Scanner):
    """ICT-style FVG + MSS entry scanner."""

    timeframe = "daily"
    description = "ICT-style FVG + MSS entry detection (50-79% zone)"

    # Constants
    MIN_CANDLES = 100
    MSS_LOOKBACK = 20
    MIN_FVG_GAP_PCT = 0.75
    MAX_MERGED_ZONE_PCT = 5.0

    def scan(self, context: ScanContext) -> List[ScanResult]:
        """Run scanner — detect FVG + MSS entries.

        Entry conditions:
        1. Unmitigated FVG exists (≥0.75%, merged, max 5% zone size)
        2. MSS confirmed (close beyond broken swing)
        3. Current price in 50-79% Fibonacci zone
        4. FVG formed before MSS (fresh setup)
        """
        candles = context.daily_candles
        results: List[ScanResult] = []

        # Step 1: Check for sufficient candles
        if len(candles) < self.MIN_CANDLES:
            logger.debug(f"Insufficient candles: {len(candles)} < {self.MIN_CANDLES}")
            return results

        # Step 2: Detect swings using FractalSwings
        swing_detector = FractalSwings()
        swings = swing_detector.detect_swings(candles)
        swing_highs = [s for s in swings if s.is_high]
        swing_lows = [s for s in swings if not s.is_high]

        if len(swing_highs) < 3 or len(swing_lows) < 3:
            logger.debug("Insufficient swings for detection")
            return results

        # Step 3: Detect FVGs using FVGDetector
        fvg_detector = FVGDetector()
        all_fvgs = fvg_detector.detect_fvgs(candles)

        if not all_fvgs:
            logger.debug("No FVGs detected")
            return results

        # Step 4: Merge overlapping FVGs
        merged_fvgs = fvg_detector.merge_fvgs(all_fvgs)

        # Step 5: Filter by zone size (max 5%)
        filtered_fvgs = []
        for fvg in merged_fvgs:
            zone_pct = ((fvg.top - fvg.bottom) / fvg.bottom) * 100
            if zone_pct <= self.MAX_MERGED_ZONE_PCT:
                filtered_fvgs.append(fvg)
            else:
                logger.debug(f"FVG zone too large: {zone_pct:.2f}% > {self.MAX_MERGED_ZONE_PCT}%")

        if not filtered_fvgs:
            logger.debug("No FVGs after size filtering")
            return results

        # Step 6: Check mitigation status
        unmitigated_fvgs = []
        for fvg in filtered_fvgs:
            # Only check candles after the FVG formation
            candles_after_fvg = candles[fvg.candle_index + 3 :]
            is_mitigated = fvg_detector.check_mitigation(fvg, candles_after_fvg)
            if not is_mitigated:
                unmitigated_fvgs.append(fvg)

        if not unmitigated_fvgs:
            logger.debug("All FVGs are mitigated")
            return results

        # Step 7: Detect MSS
        mss_info = self.detect_mss(context)
        if not mss_info or not mss_info.get("mss_confirmed"):
            logger.debug("No MSS confirmation detected")
            return results

        mss_candle_index = mss_info["mss_candle_index"]
        mss_type = mss_info["bos_type"]

        # Step 8: For each unmitigated FVG formed before MSS
        latest_close = float(candles[-1].close)

        for fvg in unmitigated_fvgs:
            # FVG must be formed before MSS
            if fvg.candle_index >= mss_candle_index:
                logger.debug(
                    f"FVG at index {fvg.candle_index} formed after MSS at {mss_candle_index}"
                )
                continue

            # Calculate Fib levels (50%, 61.8%, 79%)
            fib_levels = self.calculate_fib_levels(fvg.top, fvg.bottom)

            # Check if current close is in 50-79% zone
            fib_50 = fib_levels["fib_50"]
            fib_79 = fib_levels["fib_79"]

            if fib_79 <= latest_close <= fib_50:
                # Entry signal! All conditions met
                result = ScanResult(
                    stock_id=context.stock_id,
                    scanner_name=self.__class__.__name__,
                    metadata={
                        "symbol": context.symbol,
                        "fvg_top": fvg.top,
                        "fvg_bottom": fvg.bottom,
                        "fvg_candle_index": fvg.candle_index,
                        "fib_50": fib_50,
                        "fib_618": fib_levels["fib_618"],
                        "fib_79": fib_79,
                        "current_price": latest_close,
                        "bos_type": mss_type,
                        "bos_candle_index": mss_info["bos_candle_index"],
                        "broken_swing_price": mss_info["broken_swing_price"],
                        "mss_candle_index": mss_candle_index,
                        "fvg_bullish": fvg.bullish,
                        "entry_zone": f"{fib_79:.2f}-{fib_50:.2f}",
                    },
                )
                results.append(result)
                logger.info(
                    f"Entry signal: {context.symbol} @ {latest_close:.2f} "
                    f"in Fib zone {fib_79:.2f}-{fib_50:.2f}"
                )

        return results

    def calculate_fib_levels(self, fvg_top: float, fvg_bottom: float) -> Dict[str, float]:
        """Calculate Fibonacci retracement levels for FVG zone.

        Args:
            fvg_top: Top of FVG zone
            fvg_bottom: Bottom of FVG zone

        Returns:
            Dict with fib_50, fib_618, fib_79 levels
        """
        fvg_height = fvg_top - fvg_bottom

        return {
            "fib_50": fvg_top - (fvg_height * 0.50),
            "fib_618": fvg_top - (fvg_height * 0.618),
            "fib_79": fvg_top - (fvg_height * 0.79),
        }

    def detect_bos(self, context: ScanContext, swing_highs_only: bool = False) -> Optional[Dict]:
        """Detect Break of Structure (BOS).

        Args:
            context: Scan context with candles
            swing_highs_only: If True, only check for bullish BOS

        Returns:
            Dict with BOS info or None if no BOS detected
        """
        candles = context.daily_candles

        if len(candles) < self.MIN_CANDLES:
            return None

        # Detect swings
        swing_detector = FractalSwings()
        swings = swing_detector.detect_swings(candles)

        swing_highs = [s for s in swings if s.is_high]
        swing_lows = [s for s in swings if not s.is_high]

        if len(swing_highs) < 3 or len(swing_lows) < 3:
            return None

        latest_close = float(candles[-1].close)

        # Check for bullish BOS: close above most recent swing high
        if len(swing_highs) > 0:
            recent_swing_high = swing_highs[-1]
            if latest_close > recent_swing_high.price:
                return {
                    "type": "bullish",
                    "price": recent_swing_high.price,
                    "candle_index": recent_swing_high.candle_index,
                }

        # Check for bearish BOS: close below most recent swing low
        if not swing_highs_only and len(swing_lows) > 0:
            recent_swing_low = swing_lows[-1]
            if latest_close < recent_swing_low.price:
                return {
                    "type": "bearish",
                    "price": recent_swing_low.price,
                    "candle_index": recent_swing_low.candle_index,
                }

        return None

    def detect_mss(self, context: ScanContext) -> Optional[Dict]:
        """Detect Market Structure Shift (MSS) confirmation.

        MSS occurs after BOS when price retests and closes beyond broken swing.
        Bullish MSS: BOS up, then close below broken swing high
        Bearish MSS: BOS down, then close above broken swing low

        Returns:
            Dict with MSS state or None if no MSS detected
        """
        candles = context.daily_candles

        if len(candles) < self.MIN_CANDLES:
            return None

        # Detect swings
        swing_detector = FractalSwings()
        swings = swing_detector.detect_swings(candles)

        swing_highs = [s for s in swings if s.is_high]
        swing_lows = [s for s in swings if not s.is_high]

        if len(swing_highs) < 3 or len(swing_lows) < 3:
            return None

        # Check for bullish BOS then MSS (iterate through recent swing highs)
        for swing_high in swing_highs[-5:]:  # Check last 5 swing highs
            # Look for BOS within lookback window after the swing high
            start_idx = max(swing_high.candle_index + 1, len(candles) - self.MSS_LOOKBACK)

            for i in range(start_idx, len(candles)):
                candle_close = float(candles[i].close)

                # Bullish BOS: closed above swing high
                if candle_close > swing_high.price:
                    # Now look for MSS in subsequent candles
                    for j in range(i + 1, len(candles)):
                        subsequent_close = float(candles[j].close)

                        # Bullish MSS: closed below the broken swing high
                        if subsequent_close < swing_high.price:
                            return {
                                "bos_type": "bullish",
                                "bos_candle_index": i,
                                "broken_swing_price": swing_high.price,
                                "mss_confirmed": True,
                                "mss_candle_index": j,
                            }

        # Check for bearish BOS then MSS (iterate through recent swing lows)
        for swing_low in swing_lows[-5:]:  # Check last 5 swing lows
            # Look for BOS within lookback window after the swing low
            start_idx = max(swing_low.candle_index + 1, len(candles) - self.MSS_LOOKBACK)

            for i in range(start_idx, len(candles)):
                candle_close = float(candles[i].close)

                # Bearish BOS: closed below swing low
                if candle_close < swing_low.price:
                    # Now look for MSS in subsequent candles
                    for j in range(i + 1, len(candles)):
                        subsequent_close = float(candles[j].close)

                        # Bearish MSS: closed above the broken swing low
                        if subsequent_close > swing_low.price:
                            return {
                                "bos_type": "bearish",
                                "bos_candle_index": i,
                                "broken_swing_price": swing_low.price,
                                "mss_confirmed": True,
                                "mss_candle_index": j,
                            }

        return None
