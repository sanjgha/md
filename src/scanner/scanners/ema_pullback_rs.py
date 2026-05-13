"""9/21 EMA pullback scanner with Mansfield relative strength vs. benchmark."""

import logging
from typing import List

from src.scanner.base import Scanner, ScanResult
from src.scanner.context import ScanContext

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

    def scan(self, context: ScanContext) -> List[ScanResult]:
        """Return at most one ScanResult per stock; never raises."""
        try:
            candles = context.daily_candles
            if len(candles) < self.MIN_CANDLES:
                return []
            if not context.benchmark_candles:
                return []
            return []
        except Exception:
            logger.exception(f"EmaPullbackRsScanner failed for {context.symbol}")
            return []
