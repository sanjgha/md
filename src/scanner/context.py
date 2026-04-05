"""Scan context module for passing data to scanner instances."""

from dataclasses import dataclass
from typing import Dict, List
import numpy as np
from src.data_provider.base import Candle
from src.scanner.indicators.cache import IndicatorCache


@dataclass
class ScanContext:
    """Context passed to scanners during execution."""

    stock_id: int
    symbol: str
    daily_candles: List[Candle]
    intraday_candles: Dict[str, List[Candle]]
    indicator_cache: IndicatorCache

    def get_indicator(self, name: str, **kwargs) -> np.ndarray:
        """Retrieve (or calculate once) an indicator from the cache."""
        return self.indicator_cache.get_or_compute(name, self.daily_candles, **kwargs)
