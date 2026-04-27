"""ICT-style Smart Money scanner with FVG + MSS entry detection."""

import logging
from typing import List, Dict, Optional
from src.scanner.base import Scanner, ScanResult
from src.scanner.context import ScanContext
from src.scanner.indicators.patterns.fvg import FractalSwings

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
        """Run scanner — detect FVG + MSS entries."""
        # Full implementation in later tasks
        pass

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
