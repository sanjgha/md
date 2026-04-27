"""Fair Value Gap (FVG) detection indicator."""

from dataclasses import dataclass
from datetime import datetime
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

    def check_mitigation(self, fvg: FVGZone, candles: List[Candle]) -> bool:
        """Check if FVG has been mitigated (filled by price).

        Bullish FVG mitigated: any candle closes below FVG.bottom
        Bearish FVG mitigated: any candle closes above FVG.top
        """
        for candle in candles:
            if fvg.bullish:
                if candle.close < fvg.bottom:
                    return True
            else:
                if candle.close > fvg.top:
                    return True
        return False


@dataclass
class SwingPoint:
    """Represents a fractal swing high or low."""

    price: float
    is_high: bool
    candle_index: int
    timestamp: datetime


class FractalSwings:
    """Detects 5-bar fractal swing highs and lows."""

    def detect_swings(self, candles: List[Candle]) -> List[SwingPoint]:
        """Detect all swing highs and lows using 5-bar fractal."""
        if len(candles) < 5:
            return []

        swings = []

        # Need 2 candles on each side: [i-2, i-1, i, i+1, i+2]
        for i in range(2, len(candles) - 2):
            candle = candles[i]

            # Check for swing high
            if self._is_swing_high(candles, i):
                swings.append(
                    SwingPoint(
                        price=float(candle.high),
                        is_high=True,
                        candle_index=i,
                        timestamp=candle.timestamp,
                    )
                )

            # Check for swing low
            elif self._is_swing_low(candles, i):
                swings.append(
                    SwingPoint(
                        price=float(candle.low),
                        is_high=False,
                        candle_index=i,
                        timestamp=candle.timestamp,
                    )
                )

        return swings

    def _is_swing_high(self, candles: List[Candle], index: int) -> bool:
        """Check if candle at index is a swing high."""
        current = candles[index]

        return (
            candles[index - 2].high < current.high
            and candles[index - 1].high < current.high
            and current.high > candles[index + 1].high
            and current.high > candles[index + 2].high
        )

    def _is_swing_low(self, candles: List[Candle], index: int) -> bool:
        """Check if candle at index is a swing low."""
        current = candles[index]

        return (
            candles[index - 2].low > current.low
            and candles[index - 1].low > current.low
            and current.low < candles[index + 1].low
            and current.low < candles[index + 2].low
        )
