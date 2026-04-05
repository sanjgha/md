"""Abstract base class for all technical indicators."""

from abc import ABC, abstractmethod
import numpy as np
from typing import List
from src.data_provider.base import Candle


class Indicator(ABC):
    """Abstract base for all technical indicators."""

    @abstractmethod
    def compute(self, candles: List[Candle], **kwargs) -> np.ndarray:
        """Compute indicator values and return a numpy array."""
        pass
