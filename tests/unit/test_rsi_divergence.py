"""Unit tests for rsi_divergence helper."""

import numpy as np

from src.scanner.indicators.momentum import rsi_divergence


def test_rsi_divergence_bullish():
    """Lower price low + higher RSI low → bullish_div=True, bearish_div=False."""
    prices = np.array([100.0, 90.0, 95.0, 85.0])
    rsi = np.array([55.0, 30.0, 50.0, 35.0])
    bull, bear = rsi_divergence(prices, rsi, prior_pivot=1, current_pivot=3)
    assert bull is True
    assert bear is False


def test_rsi_divergence_bearish():
    """Higher price high + lower RSI high → bearish_div=True."""
    prices = np.array([100.0, 110.0, 105.0, 115.0])
    rsi = np.array([55.0, 80.0, 60.0, 70.0])
    bull, bear = rsi_divergence(prices, rsi, prior_pivot=1, current_pivot=3)
    assert bear is True
    assert bull is False


def test_rsi_divergence_none():
    """Both lows higher and both RSI lows higher → no divergence either side."""
    prices = np.array([100.0, 90.0, 95.0, 92.0])
    rsi = np.array([55.0, 30.0, 50.0, 35.0])
    bull, bear = rsi_divergence(prices, rsi, prior_pivot=1, current_pivot=3)
    assert bull is False
    assert bear is False
