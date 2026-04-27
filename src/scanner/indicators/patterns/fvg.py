"""Fair Value Gap (FVG) detection indicator."""

from dataclasses import dataclass
from typing import List
from src.data_provider.base import Candle


@dataclass
class FVGZone:
    """Represents a Fair Value Gap zone."""

    top: float
    bottom: float
    bullish: bool
    candle_index: int
    mitigated: bool = False


class FVGDetector:
    """Detects Fair Value Gaps (3-candle imbalance patterns)."""

    MIN_GAP_PCT = 0.75  # Minimum gap size as percentage of price

    def detect_fvgs(self, candles: List[Candle]) -> List[FVGZone]:
        """Detect all FVGs in the candle sequence."""
        if len(candles) < 3:
            return []

        fvgs = []

        # Need at least 3 candles: i, i+1, i+2
        for i in range(len(candles) - 2):
            candle_i = candles[i]
            candle_i2 = candles[i + 2]

            # Check for bullish FVG: gap up
            if candle_i.high < candle_i2.low:
                gap_size = abs(candle_i2.low - candle_i.high)
                gap_pct = (gap_size / candle_i.high) * 100

                if gap_pct >= self.MIN_GAP_PCT:
                    fvgs.append(
                        FVGZone(
                            top=float(candle_i2.low),
                            bottom=float(candle_i.high),
                            bullish=True,
                            candle_index=i,
                        )
                    )

            # Check for bearish FVG: gap down
            elif candle_i.low > candle_i2.high:
                gap_size = abs(candle_i.low - candle_i2.high)
                gap_pct = (gap_size / candle_i2.high) * 100

                if gap_pct >= self.MIN_GAP_PCT:
                    fvgs.append(
                        FVGZone(
                            top=float(candle_i.low),
                            bottom=float(candle_i2.high),
                            bullish=False,
                            candle_index=i,
                        )
                    )

        return fvgs

    def merge_fvgs(self, fvgs: List[FVGZone]) -> List[FVGZone]:
        """Merge overlapping FVG zones into single zones."""
        if not fvgs:
            return []

        # Sort by bottom price
        sorted_fvgs = sorted(fvgs, key=lambda f: f.bottom)

        merged = [sorted_fvgs[0]]

        for current in sorted_fvgs[1:]:
            last = merged[-1]

            # Check if overlapping: max(bottom1, bottom2) < min(top1, top2)
            overlap_bottom = max(last.bottom, current.bottom)
            overlap_top = min(last.top, current.top)

            if overlap_bottom < overlap_top:
                # Overlapping — merge by expanding the zone
                merged[-1] = FVGZone(
                    top=max(last.top, current.top),
                    bottom=min(last.bottom, current.bottom),
                    bullish=last.bullish,  # Assume same direction
                    candle_index=last.candle_index,
                    mitigated=last.mitigated or current.mitigated,
                )
            else:
                # No overlap — keep separate
                merged.append(current)

        return merged
