# tests/unit/test_indicator_cache.py
import numpy as np
from datetime import datetime
from src.scanner.indicators.cache import IndicatorCache
from src.scanner.indicators.base import Indicator
from src.data_provider.base import Candle


class MockIndicator(Indicator):
    def compute(self, candles, **kwargs):
        return np.array([c.close for c in candles])


def make_candles(n=3):
    return [Candle(datetime.now(), 100 + i, 102 + i, 99 + i, 101 + i, 1000) for i in range(n)]


def test_indicator_cache_computes_once():
    cache = IndicatorCache({"mock": MockIndicator()})
    candles = make_candles(2)
    result1 = cache.get_or_compute("mock", candles)
    result2 = cache.get_or_compute("mock", candles)
    assert result1 is result2
    assert len(result1) == 2


def test_indicator_cache_different_kwargs():
    cache = IndicatorCache({"mock": MockIndicator()})
    candles = make_candles(1)
    result1 = cache.get_or_compute("mock", candles, period=10)
    result2 = cache.get_or_compute("mock", candles, period=20)
    assert result1 is not result2


def test_indicator_cache_clear():
    cache = IndicatorCache({"mock": MockIndicator()})
    candles = make_candles(2)
    r1 = cache.get_or_compute("mock", candles)
    cache.clear()
    r2 = cache.get_or_compute("mock", candles)
    assert r1 is not r2
