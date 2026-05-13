"""Unit tests for ema_pullback_rs scanner."""

from datetime import datetime, timedelta
from typing import List
from src.data_provider.base import Candle
from src.scanner.context import ScanContext
from src.scanner.indicators.cache import IndicatorCache
from src.scanner.indicators.moving_averages import EMA
from src.scanner.indicators.momentum import RSI
from src.scanner.indicators.volatility import ATR
from src.scanner.scanners.ema_pullback_rs import EmaPullbackRsScanner


# ---------- Test helpers ----------

INDICATORS = {"ema": EMA(), "rsi": RSI(), "atr": ATR()}


def _ctx(
    daily: List[Candle], bench: List[Candle], stock_id: int = 1, symbol: str = "AAPL"
) -> ScanContext:
    return ScanContext(
        stock_id=stock_id,
        symbol=symbol,
        daily_candles=daily,
        intraday_candles={},
        indicator_cache=IndicatorCache(INDICATORS),
        benchmark_candles=bench,
    )


def _candles(
    closes: List[float], start: datetime | None = None, volume: int = 5_000_000
) -> List[Candle]:
    start = start or datetime(2024, 1, 1)
    return [
        Candle(
            timestamp=start + timedelta(days=i),
            open=c * 0.999,
            high=c * 1.005,
            low=c * 0.995,
            close=c,
            volume=volume,
        )
        for i, c in enumerate(closes)
    ]


# ---------- Skeleton tests ----------


def test_scanner_class_attributes():
    scanner = EmaPullbackRsScanner()
    assert scanner.timeframe == "daily"
    assert "9/21" in scanner.description
    assert scanner.MIN_CANDLES == 280
    assert scanner.PRICE_MIN == 20.0
    assert scanner.BENCHMARK_SYMBOL == "SPY"
    assert scanner.RS_SMA_PERIOD == 260
    assert scanner.RS_SLOPE_LOOKBACK == 21
    assert scanner.PULLBACK_WINDOW == 5
    assert scanner.RSI_MIN == 40.0
    assert scanner.RSI_MAX == 70.0


def test_returns_empty_when_below_min_candles():
    daily = _candles([100.0] * 50)
    bench = _candles([100.0] * 50)
    assert EmaPullbackRsScanner().scan(_ctx(daily, bench)) == []


def test_returns_empty_when_benchmark_candles_missing():
    daily = _candles([100.0] * 300)
    assert EmaPullbackRsScanner().scan(_ctx(daily, bench=[])) == []
