"""Unit tests for PullbackContinuationScanner."""

from datetime import datetime, timedelta
from typing import List

from src.data_provider.base import Candle
from src.scanner.context import ScanContext
from src.scanner.indicators.cache import IndicatorCache
from src.scanner.indicators.moving_averages import EMA
from src.scanner.indicators.momentum import RSI, MACD
from src.scanner.indicators.volatility import ATR
from src.scanner.indicators.support_resistance import SwingPoints
from src.scanner.scanners.pullback_continuation import PullbackContinuationScanner


def _make_indicators():
    return {
        "ema": EMA(),
        "rsi": RSI(),
        "macd": MACD(),
        "atr": ATR(),
        "swing_points": SwingPoints(),
    }


def _make_context(candles: List[Candle], stock_id: int = 1, symbol: str = "TEST") -> ScanContext:
    return ScanContext(
        stock_id=stock_id,
        symbol=symbol,
        daily_candles=candles,
        intraday_candles={},
        indicator_cache=IndicatorCache(_make_indicators()),
    )


def test_scanner_returns_empty_list_with_too_few_candles():
    """< 80 candles → returns []."""
    base_dt = datetime(2024, 1, 1)
    candles = [
        Candle(base_dt + timedelta(days=i), 100.0, 101.0, 99.0, 100.0, 5_000_000) for i in range(50)
    ]
    scanner = PullbackContinuationScanner()
    assert scanner.scan(_make_context(candles)) == []


def _bullish_pullback_candles(
    *,
    pullback_low_offset: float = 0.0,
    swing_high_offset: int = 0,
    trigger_close: float = 165.0,
    trigger_volume: int = 5_000_000,
    base_volume: int = 2_000_000,
) -> List[Candle]:
    """80 candles producing a clean long pullback continuation setup.

    Phase 1a (50 bars): steady uptrend 80 → 130 (locks EMA stack and positive EMA(50) slope).
    Phase 1b (10 bars): minor dip + recovery 130 → 125 → 136 — creates an early swing low
                        used as L for the up-leg measurement.
    Phase 2  (8 bars):  rise to swing high (H) at index 65 (~163), then sharp drop.
    Phase 3  (11 bars): pullback bottoms ~145 then drifts back up to ~155;
                        last bar carries a volume surge.
    Phase 4  (1 bar):   trigger today (index 79) — close > EMA(9) AND > 3-bar high;
                        volume surge.
    """
    base_dt = datetime(2024, 1, 1)
    candles: List[Candle] = []

    # Phase 1a: 50 bars rising 80 → 130
    for i in range(50):
        price = 80.0 + i * (50.0 / 49.0)
        candles.append(
            Candle(
                timestamp=base_dt + timedelta(days=i),
                open=price,
                high=price + 1.0,
                low=price - 1.0,
                close=price,
                volume=base_volume,
            )
        )

    # Phase 1b: 10 bars dip + recovery — creates a fractal swing low (L) at idx 53.
    dip = [130.0, 128.0, 126.0, 125.0, 126.0, 128.0, 130.0, 132.0, 134.0, 136.0]
    for i, price in enumerate(dip):
        candles.append(
            Candle(
                timestamp=base_dt + timedelta(days=50 + i),
                open=price,
                high=price + 1.0,
                low=price - 1.0,
                close=price,
                volume=base_volume,
            )
        )

    # Phase 2: rise to swing high (H) at idx 65, then drop. 8 bars — idx 60..67.
    leg = [140.0, 145.0, 150.0, 155.0, 160.0, 162.0, 158.0, 152.0]
    for i, price in enumerate(leg):
        candles.append(
            Candle(
                timestamp=base_dt + timedelta(days=60 + i),
                open=price,
                high=price + 1.0,
                low=price - 1.0,
                close=price,
                volume=base_volume,
            )
        )

    # Phase 3: pullback bottoms at idx 70 then drifts up. 11 bars idx 68..78.
    consolidation = [
        148.0,
        146.0,
        145.0 + pullback_low_offset,
        146.0,
        147.0,
        148.0,
        149.0,
        150.5,
        152.0,
        153.5,
        155.0,
    ]
    for i, price in enumerate(consolidation):
        vol = int(base_volume * 1.3) if i == len(consolidation) - 1 else base_volume
        candles.append(
            Candle(
                timestamp=base_dt + timedelta(days=68 + i),
                open=price,
                high=price + 1.0,
                low=price - 1.0,
                close=price,
                volume=vol,
            )
        )

    # Phase 4: trigger today (index 79) — close above 3-bar high, volume surge.
    candles.append(
        Candle(
            timestamp=base_dt + timedelta(days=79),
            open=156.0,
            high=trigger_close + 1.0,
            low=155.5,
            close=trigger_close,
            volume=trigger_volume,
        )
    )
    return candles


def _bearish_failed_bounce_candles(
    *, trigger_close: float = 138.0, trigger_volume: int = 5_000_000
) -> List[Candle]:
    """80 candles where uptrend was confirmed at bar H, broke at bar L, today rejects bounce.

    Phase 1 (55 bars): uptrend 80 → 160.
    Phase 2 (12 bars): swing high, sharp drop through EMA(21) to swing low at ~140.
    Phase 3 (12 bars): bounce up to ~150, fails near resistance, MACD rolls negative.
    Phase 4 (1 bar):   trigger — close < EMA(21), close below 3-bar low, volume surge.
    """
    base_dt = datetime(2024, 1, 1)
    candles: List[Candle] = []

    # Phase 1: uptrend
    for i in range(55):
        price = 80.0 + i * (80.0 / 54.0)
        candles.append(
            Candle(
                timestamp=base_dt + timedelta(days=i),
                open=price,
                high=price + 1.0,
                low=price - 1.0,
                close=price,
                volume=2_000_000,
            )
        )

    # Phase 2: drop through to swing low (12 bars)
    drop = [161.0, 160.0, 158.0, 154.0, 150.0, 146.0, 143.0, 141.0, 140.0, 140.5, 140.0, 139.5]
    for i, price in enumerate(drop):
        candles.append(
            Candle(
                timestamp=base_dt + timedelta(days=55 + i),
                open=price,
                high=price + 1.0,
                low=price - 1.0,
                close=price,
                volume=2_000_000,
            )
        )

    # Phase 3: bounce that fails (12 bars)
    bounce = [142.0, 145.0, 148.0, 150.0, 151.0, 150.5, 149.0, 147.0, 145.0, 143.0, 141.0]
    for i, price in enumerate(bounce):
        vol = 2_600_000 if i == len(bounce) - 1 else 2_000_000  # volume surge on last
        candles.append(
            Candle(
                timestamp=base_dt + timedelta(days=67 + i),
                open=price,
                high=price + 1.0,
                low=price - 1.0,
                close=price,
                volume=vol,
            )
        )

    # Phase 4: trigger today (index 79) — close below 3-bar low, volume surge
    candles.append(
        Candle(
            timestamp=base_dt + timedelta(days=79),
            open=141.0,
            high=141.5,
            low=trigger_close - 1.0,
            close=trigger_close,
            volume=trigger_volume,
        )
    )
    return candles


def test_universe_filter_price():
    """close < $20 → no signal."""
    base_dt = datetime(2024, 1, 1)
    cheap = [
        Candle(base_dt + timedelta(days=i), 15.0, 16.0, 14.0, 15.0, 5_000_000) for i in range(80)
    ]
    scanner = PullbackContinuationScanner()
    assert scanner.scan(_make_context(cheap)) == []


def test_universe_filter_dollar_volume():
    """avg dollar volume < $50M → no signal."""
    base_dt = datetime(2024, 1, 1)
    thin = [Candle(base_dt + timedelta(days=i), 25.0, 26.0, 24.0, 25.0, 100) for i in range(80)]
    scanner = PullbackContinuationScanner()
    assert scanner.scan(_make_context(thin)) == []


def test_universe_filter_atr():
    """ATR% < 1.5 → no signal (tight series)."""
    base_dt = datetime(2024, 1, 1)
    flat = [
        Candle(base_dt + timedelta(days=i), 100.0, 100.05, 99.95, 100.0, 5_000_000)
        for i in range(80)
    ]
    scanner = PullbackContinuationScanner()
    assert scanner.scan(_make_context(flat)) == []


def test_no_signal_when_pullback_too_shallow():
    """retrace 25% → no signal (below 0.38 floor)."""
    candles = _bullish_pullback_candles(pullback_low_offset=8.0)
    scanner = PullbackContinuationScanner()
    results = scanner.scan(_make_context(candles))
    assert results == []


def test_no_signal_when_pullback_too_deep():
    """retrace 85% → no signal (above 0.78 ceiling)."""
    candles = _bullish_pullback_candles(pullback_low_offset=-15.0)
    scanner = PullbackContinuationScanner()
    results = scanner.scan(_make_context(candles))
    assert results == []


def test_emits_long_on_clean_pullback():
    """Trend up, retrace ~50%, ≥2 exhaustion, trigger today → exactly one long signal."""
    candles = _bullish_pullback_candles()
    scanner = PullbackContinuationScanner()
    results = scanner.scan(_make_context(candles))
    assert len(results) == 1
    r = results[0]
    assert r.scanner_name == "pullback_continuation"
    assert r.metadata["direction"] == "long"
    assert r.metadata["exhaustion_count"] >= 2
    assert 0.38 <= r.metadata["retrace_pct"] <= 0.78
