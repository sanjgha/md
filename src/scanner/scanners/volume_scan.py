"""Volume scanner: detects spikes relative to the 20-day average volume."""

import logging
import numpy as np
from typing import List
from src.scanner.base import Scanner, ScanResult
from src.scanner.context import ScanContext

logger = logging.getLogger(__name__)


class VolumeScanner(Scanner):
    """Scan for volume spikes relative to 20-day average."""

    def scan(self, context: ScanContext) -> List[ScanResult]:
        """Return match when latest volume exceeds 2x the prior 20-day average."""
        matches = []

        if len(context.daily_candles) < 21:
            return matches

        try:
            closes = np.array([float(c.close) for c in context.daily_candles])
            volumes = np.array([float(c.volume) for c in context.daily_candles])

            avg_volume = np.mean(volumes[-21:-1])  # Prior 20 days, not today
            latest_volume = volumes[-1]

            if latest_volume > 2.0 * avg_volume:
                direction = "up" if closes[-1] > closes[-2] else "down"
                matches.append(
                    ScanResult(
                        stock_id=context.stock_id,
                        scanner_name="volume",
                        metadata={
                            "reason": f"volume_spike_{direction}",
                            "volume": float(latest_volume),
                            "avg_volume_20d": float(avg_volume),
                            "ratio": round(float(latest_volume / avg_volume), 2),
                        },
                    )
                )
        except Exception:
            logger.exception(f"VolumeScanner failed for {context.symbol}")

        return matches
