"""Momentum scanner: detects RSI oversold and overbought conditions."""

import logging
from typing import List
from src.scanner.base import Scanner, ScanResult
from src.scanner.context import ScanContext

logger = logging.getLogger(__name__)


class MomentumScanner(Scanner):
    """Scan for RSI oversold/overbought conditions."""

    def scan(self, context: ScanContext) -> List[ScanResult]:
        """Return matches when RSI-14 is below 30 (oversold) or above 70 (overbought)."""
        matches: List[ScanResult] = []

        if len(context.daily_candles) < 50:
            return matches

        try:
            rsi = context.get_indicator("rsi", period=14)

            if len(rsi) == 0:
                return matches

            latest_rsi = float(rsi[-1])

            if latest_rsi < 30:
                matches.append(
                    ScanResult(
                        stock_id=context.stock_id,
                        scanner_name="momentum",
                        metadata={"reason": "oversold", "rsi": latest_rsi},
                    )
                )
            elif latest_rsi > 70:
                matches.append(
                    ScanResult(
                        stock_id=context.stock_id,
                        scanner_name="momentum",
                        metadata={"reason": "overbought", "rsi": latest_rsi},
                    )
                )
        except Exception:
            logger.exception(f"MomentumScanner failed for {context.symbol}")

        return matches
