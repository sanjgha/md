"""Six-month high scanner: detects stocks that hit 6-month high (close) in past 5 trading days."""

import logging
from typing import List
from src.scanner.base import Scanner, ScanResult
from src.scanner.context import ScanContext

logger = logging.getLogger(__name__)


class SixMonthHighScanner(Scanner):
    """Scan for stocks that hit 6-month high (close price) in past 5 trading days."""

    timeframe = "daily"
    description = "Stocks that hit 6-month high (close) in past 5 trading days"

    def scan(self, context: ScanContext) -> List[ScanResult]:
        """Return matches when close price broke 6-month high in last 5 trading days.

        Algorithm:
        1. Need at least 131 candles (126 for reference window + 5 for lookback)
        2. Compute rolling_max with period=126
        3. Get reference high from rolling_max[-6] (6-month high as of 6 days ago)
        4. Check if any of last 5 candles (indices -5 to -1) exceed this reference
        5. Return only the most recent match if multiple found

        Args:
            context: ScanContext with daily_candles and indicator_cache

        Returns:
            List of ScanResult (empty or single result with most recent match)
        """
        matches: List[ScanResult] = []

        # Need at least 131 candles: 126 for 6-month window + 5 for lookback
        if len(context.daily_candles) < 131:
            return matches

        try:
            # Get rolling maximum indicator with 126-period window (~6 trading months)
            rolling_max = context.get_indicator("rolling_max", period=126)

            if len(rolling_max) < 6:
                return matches

            # Reference high: 6-month high as of 6 days ago (before lookback window)
            six_month_high = float(rolling_max[-6])

            # Check last 5 candles for new 6-month highs
            # Indices: -5 (5 days ago), -4, -3, -2, -1 (today)
            most_recent_match_idx = None
            most_recent_match_close = None

            for offset in range(-5, 0):  # -5, -4, -3, -2, -1
                candle = context.daily_candles[offset]
                if candle.close > six_month_high:
                    most_recent_match_idx = offset
                    most_recent_match_close = candle.close

            # If we found a match, create ScanResult for the most recent one
            if most_recent_match_idx is not None:
                # Calculate days_ago: offset -1 = 0 days, offset -2 = 1 day, etc.
                days_ago = abs(most_recent_match_idx + 1)
                match_candle = context.daily_candles[most_recent_match_idx]

                matches.append(
                    ScanResult(
                        stock_id=context.stock_id,
                        scanner_name="six_month_high",
                        metadata={
                            "six_month_high": six_month_high,
                            "current_close": most_recent_match_close,
                            "days_ago": days_ago,
                            "high_date": match_candle.timestamp.strftime("%Y-%m-%d"),
                        },
                    )
                )

        except Exception:
            logger.exception(f"SixMonthHighScanner failed for {context.symbol}")

        return matches
