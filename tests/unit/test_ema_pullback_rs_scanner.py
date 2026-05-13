"""Unit tests for ema_pullback_rs scanner."""

from datetime import datetime, timedelta
from typing import List

import numpy as np

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


def test_rejects_when_price_below_min():
    # 300 bars but final close is $10 — below PRICE_MIN of $20.
    daily = _candles([100.0] * 295 + [15.0, 12.0, 11.0, 10.5, 10.0])
    bench = _candles([100.0] * 300)
    assert EmaPullbackRsScanner().scan(_ctx(daily, bench)) == []


def test_rejects_when_dollar_volume_below_min():
    # Price OK but volume tiny → dollar volume below threshold.
    daily = _candles([100.0] * 300, volume=10_000)
    bench = _candles([100.0] * 300)
    assert EmaPullbackRsScanner().scan(_ctx(daily, bench)) == []


def test_rejects_when_atr_pct_below_min():
    # Flat candles → ATR ~0 → ATR% well below 1.5.
    daily = _candles([100.0] * 300, volume=5_000_000)
    bench = _candles([100.0] * 300)
    assert EmaPullbackRsScanner().scan(_ctx(daily, bench)) == []


def test_rejects_when_ema_stack_not_aligned():
    # Downtrend → EMA_9 < EMA_21 < EMA_50, the wrong order for our long-only filter.
    closes = list(np.linspace(150, 100, 300))
    daily = _candles(closes)
    bench = _candles([100.0] * 300)
    assert EmaPullbackRsScanner().scan(_ctx(daily, bench)) == []


def test_rejects_when_ema_50_not_rising():
    # Flat closes → EMA_50 slope = 0; flat is not > 0.
    daily = _candles([100.0] * 300, volume=5_000_000)
    bench = _candles([100.0] * 300)
    assert EmaPullbackRsScanner().scan(_ctx(daily, bench)) == []


def _uptrend_with_pullback() -> tuple[List[Candle], List[Candle]]:
    """Build daily + benchmark candles that pass all 5 gates.

    Stock: 280 bars trending up from $50 → ~$150 with a 3-bar pullback ending 2 bars ago.
    Benchmark: 280 bars trending up from $100 → ~$110 (so stock outperforms).
    """
    n = 280
    rng = np.random.default_rng(seed=42)
    # Smooth uptrend with mild noise; final 5 bars: 2-bar pullback, 3 bars ago touches EMA_9.
    closes = list(np.linspace(50, 150, n - 5) + rng.normal(0, 0.5, n - 5))
    # Manually craft the last 5 bars to engineer a touch + reclaim.
    closes += [
        closes[-1] * 0.99,  # bar n-5
        closes[-1] * 0.96,  # bar n-4: deep pullback, will touch EMA_9
        closes[-1] * 0.96,  # bar n-3
        closes[-1] * 0.98,  # bar n-2
        closes[-1] * 1.02,  # bar n-1 (today): reclaim above EMA_9
    ]
    daily = _candles(closes)
    bench = _candles(list(np.linspace(100, 110, n)))
    return daily, bench


def test_emits_result_when_all_gates_pass():
    """Canary test — will be red until Task 7 wires up remaining gates + metadata."""
    daily, bench = _uptrend_with_pullback()
    results = EmaPullbackRsScanner().scan(_ctx(daily, bench))
    assert len(results) == 1
    assert results[0].scanner_name == "ema_pullback_rs"
