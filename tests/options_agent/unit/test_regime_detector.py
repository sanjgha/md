"""Unit tests for market regime detection."""

import numpy as np
import pandas as pd


def _trending_bars(n: int = 120, slope: float = 0.005) -> pd.DataFrame:
    """Strong uptrend bars — ADX will be high."""
    np.random.seed(1)
    closes = np.cumprod(1 + np.random.normal(slope, 0.008, n)) * 100
    high = closes * 1.005
    low = closes * 0.995
    return pd.DataFrame(
        {
            "open": closes * 0.999,
            "high": high,
            "low": low,
            "close": closes,
            "volume": [1_000_000] * n,
        }
    )


def _ranging_bars(n: int = 120) -> pd.DataFrame:
    """Tight-range bars — ADX low, ATR% small."""
    np.random.seed(2)
    closes = 100 + np.random.normal(0, 0.3, n)
    high = closes + 0.2
    low = closes - 0.2
    return pd.DataFrame(
        {"open": closes, "high": high, "low": low, "close": closes, "volume": [500_000] * n}
    )


def _spy_trending_up(n: int = 120) -> pd.DataFrame:
    """SPY bars in a clear uptrend."""
    np.random.seed(3)
    closes = np.cumprod(1 + np.random.normal(0.003, 0.006, n)) * 500
    return pd.DataFrame(
        {
            "close": closes,
            "high": closes * 1.003,
            "low": closes * 0.997,
            "open": closes,
            "volume": [50_000_000] * n,
        }
    )


def _spy_flat(n: int = 120) -> pd.DataFrame:
    """SPY bars with no trend."""
    return pd.DataFrame(
        {
            "close": [500.0] * n,
            "high": [501.0] * n,
            "low": [499.0] * n,
            "open": [500.0] * n,
            "volume": [50_000_000] * n,
        }
    )


def test_trending_bullish():
    """Trending bars with SPY up → regime=trending, direction=bullish, ADX>25."""
    from src.options_agent.signals.regime import detect_regime

    result = detect_regime(_trending_bars(), _spy_trending_up())
    assert result.regime == "trending"
    assert result.direction == "bullish"
    assert result.adx > 25


def test_ranging():
    """Ranging bars with flat SPY → regime=ranging, ADX<20."""
    from src.options_agent.signals.regime import detect_regime

    result = detect_regime(_ranging_bars(), _spy_flat())
    assert result.regime == "ranging"
    assert result.adx < 20


def test_result_dataclass_fields():
    """detect_regime returns a RegimeResult with all required fields."""
    from src.options_agent.signals.regime import detect_regime, RegimeResult

    result = detect_regime(_trending_bars(), _spy_trending_up())
    assert isinstance(result, RegimeResult)
    assert result.regime in ("trending", "ranging", "transitional")
    assert isinstance(result.adx, float)
    assert isinstance(result.atr_pct, float)
