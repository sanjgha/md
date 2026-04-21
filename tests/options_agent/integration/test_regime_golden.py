"""Golden tests for regime detection using synthetic fixtures.

These tests use hand-labelled synthetic bars to verify regime detection
correctly classifies market conditions.

Fixtures are synthetic but realistic:
- Chains: Realistic option contract structure with ATM strikes
- Bars: 500 bars each with regime-specific characteristics
"""

import pandas as pd
import pytest

from src.options_agent.signals.regime import detect_regime


@pytest.mark.parametrize(
    "fixture,expected_regime,expected_direction",
    [
        ("spy_jul2024_ranging", "ranging", "neutral"),
        ("aapl_oct2024_trending_up", "trending", "bullish"),
        ("nvda_aug2024_transitional", "transitional", "unclear"),
    ],
)
def test_regime_golden_fixtures(fixture, expected_regime, expected_direction):
    """Test regime detection against hand-labelled synthetic fixtures.

    This is a golden test: fixtures are labelled with expected regime
    based on their generation parameters. The test verifies that the
    detect_regime function correctly classifies these known patterns.
    """
    # Load fixture (skip comment lines starting with #)
    bars = pd.read_csv(f"tests/options_agent/fixtures/bars/{fixture}.csv", comment="#")

    # Use SPY as market benchmark for all tests
    spy_bars = pd.read_csv("tests/options_agent/fixtures/bars/spy_jul2024_ranging.csv", comment="#")

    result = detect_regime(bars, spy_bars)

    # Assert regime classification
    assert result.regime == expected_regime, (
        f"Expected regime '{expected_regime}' but got '{result.regime}' "
        f"(ADX={result.adx:.2f}, ATR%={result.atr_pct:.4f}, SPY_trend={result.spy_trend_20d:.4f})"
    )

    # Assert direction (except for transitional where direction is unclear)
    if expected_direction is not None:
        assert result.direction == expected_direction, (
            f"Expected direction '{expected_direction}' but got '{result.direction}' "
            f"(ADX={result.adx:.2f}, ATR%={result.atr_pct:.4f}, SPY_trend={result.spy_trend_20d:.4f})"
        )


def test_regime_ranging_characteristics():
    """Verify ranging fixture has expected characteristics."""
    bars = pd.read_csv("tests/options_agent/fixtures/bars/spy_jul2024_ranging.csv", comment="#")
    spy_bars = pd.read_csv("tests/options_agent/fixtures/bars/spy_jul2024_ranging.csv", comment="#")

    result = detect_regime(bars, spy_bars)

    # Ranging should have low ADX and low ATR%
    assert result.adx < 25, f"Ranging market should have ADX < 25, got {result.adx:.2f}"
    assert result.atr_pct < 0.02, f"Ranging market should have ATR% < 2%, got {result.atr_pct:.4f}"


def test_regime_trending_characteristics():
    """Verify trending fixture has expected characteristics."""
    bars = pd.read_csv(
        "tests/options_agent/fixtures/bars/aapl_oct2024_trending_up.csv", comment="#"
    )
    spy_bars = pd.read_csv("tests/options_agent/fixtures/bars/spy_jul2024_ranging.csv", comment="#")

    result = detect_regime(bars, spy_bars)

    # Trending should have higher ADX
    assert result.adx > 25, f"Trending market should have ADX > 25, got {result.adx:.2f}"

    # Bullish trending should have positive SPY trend or price above EMA20
    assert result.direction == "bullish", "Trending up fixture should be bullish"


def test_regime_transitional_characteristics():
    """Verify transitional fixture has expected characteristics."""
    bars = pd.read_csv(
        "tests/options_agent/fixtures/bars/nvda_aug2024_transitional.csv",
        comment="#",
    )
    spy_bars = pd.read_csv("tests/options_agent/fixtures/bars/spy_jul2024_ranging.csv", comment="#")

    result = detect_regime(bars, spy_bars)

    # Transitional is the catch-all for non-trending, non-ranging
    assert result.regime == "transitional", f"Expected transitional regime, got {result.regime}"
    assert result.direction == "unclear", "Transitional should have unclear direction"
