"""Indicator cache module to avoid recomputation during EOD scans."""

from typing import Dict, Tuple, List
import numpy as np
from src.data_provider.base import Candle
from src.scanner.indicators.base import Indicator


class IndicatorCache:
    """Cache for indicators computed during EOD run — avoids recomputation."""

    def __init__(self, indicators_registry: Dict[str, Indicator]):
        """Initialize cache with an indicators registry."""
        self.registry = indicators_registry
        self._cache: Dict[Tuple, np.ndarray] = {}

    def get_or_compute(self, name: str, candles: List[Candle], **kwargs) -> np.ndarray:
        """Return cached result or compute and cache it."""
        cache_key = (name, tuple(sorted(kwargs.items())))
        if cache_key in self._cache:
            return self._cache[cache_key]
        indicator = self.registry[name]
        result = indicator.compute(candles, **kwargs)
        self._cache[cache_key] = result
        return result

    def clear(self) -> None:
        """Clear all cached results."""
        self._cache.clear()
