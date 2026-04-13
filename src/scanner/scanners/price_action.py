"""Price action scanner: detects breakouts and bounces at SMA50/SMA200."""

import logging
from typing import List
from src.scanner.base import Scanner, ScanResult
from src.scanner.context import ScanContext

logger = logging.getLogger(__name__)


class PriceActionScanner(Scanner):
    """Scan for price action breakouts and bounces above/at SMA50/SMA200."""

    timeframe = "daily"
    description = "Price action patterns on daily candles (breakouts, support/resistance)"

    def scan(self, context: ScanContext) -> List[ScanResult]:
        """Return matches when price is above SMA50 > SMA200 and touches SMA50."""
        matches: List[ScanResult] = []

        if len(context.daily_candles) < 200:
            return matches

        try:
            sma50 = context.get_indicator("sma", period=50)
            sma200 = context.get_indicator("sma", period=200)

            latest_close = float(context.daily_candles[-1].close)
            latest_high = float(context.daily_candles[-1].high)
            latest_low = float(context.daily_candles[-1].low)

            if (
                len(sma50) > 0
                and len(sma200) > 0
                and latest_close > float(sma50[-1])
                and float(sma50[-1]) > float(sma200[-1])
            ):
                support_level = float(sma50[-1])
                if latest_low <= support_level <= latest_high:
                    matches.append(
                        ScanResult(
                            stock_id=context.stock_id,
                            scanner_name="price_action",
                            metadata={
                                "reason": "bounce_off_support",
                                "support_level": support_level,
                                "current_price": latest_close,
                            },
                        )
                    )
        except Exception:
            logger.exception(f"PriceActionScanner failed for {context.symbol}")

        return matches
