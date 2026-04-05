# tests/unit/test_indicators.py
import numpy as np
from datetime import datetime
from src.data_provider.base import Candle
from src.scanner.indicators.moving_averages import SMA, EMA, WMA
from src.scanner.indicators.momentum import RSI
from src.scanner.indicators.volatility import BollingerBands, ATR
from src.scanner.indicators.support_resistance import SupportResistance
from src.scanner.indicators.patterns.breakouts import BreakoutDetector
from src.scanner.indicators.patterns.candlestick import CandlestickPatterns


def make_candles(closes, highs=None, lows=None):
    from datetime import timedelta

    if highs is None:
        highs = [c + 1 for c in closes]
    if lows is None:
        lows = [c - 1 for c in closes]
    base = datetime(2024, 1, 1)
    return [
        Candle(base + timedelta(days=i), c, h, lo, c, 1000)
        for i, (c, h, lo) in enumerate(zip(closes, highs, lows))
    ]


# --- SMA ---
def test_sma_calculation():
    candles = make_candles([100, 101, 102, 103, 104])
    result = SMA().compute(candles, period=3)
    np.testing.assert_array_almost_equal(result, [101, 102, 103])


def test_sma_too_few_candles():
    candles = make_candles([100, 101])
    assert len(SMA().compute(candles, period=5)) == 0


# --- EMA ---
def test_ema_length_matches_sma():
    closes = list(range(100, 160))
    candles = make_candles(closes)
    sma = SMA().compute(candles, period=10)
    ema = EMA().compute(candles, period=10)
    assert len(ema) == len(sma)


def test_ema_seeded_with_sma():
    closes = [float(i) for i in range(1, 21)]
    candles = make_candles(closes)
    ema = EMA().compute(candles, period=5)
    # First value must equal SMA of first 5 values = mean([1,2,3,4,5]) = 3.0
    assert abs(ema[0] - 3.0) < 1e-9


def test_ema_too_few_candles():
    candles = make_candles([100, 101])
    assert len(EMA().compute(candles, period=5)) == 0


# --- WMA ---
def test_wma_calculation():
    candles = make_candles([10, 20, 30])
    result = WMA().compute(candles, period=3)
    # WMA([10,20,30], weights=[1,2,3]) = (10*1 + 20*2 + 30*3) / 6 = 140/6
    assert abs(result[0] - 140 / 6) < 1e-6


# --- RSI ---
def test_rsi_range():
    closes = [100 + (i % 7) * 1.5 for i in range(30)]
    candles = make_candles(closes)
    result = RSI().compute(candles, period=14)
    assert len(result) > 0
    assert all(0 <= v <= 100 for v in result)


def test_rsi_seeded_first_value():
    # If all gains, RSI should be 100
    closes = [float(i) for i in range(1, 32)]
    candles = make_candles(closes)
    result = RSI().compute(candles, period=14)
    assert abs(result[0] - 100.0) < 1e-6


def test_rsi_too_few_candles():
    candles = make_candles([100, 101])
    assert len(RSI().compute(candles, period=14)) == 0


# --- BollingerBands ---
def test_bollinger_bands_shape():
    closes = [float(100 + i % 5) for i in range(30)]
    candles = make_candles(closes)
    result = BollingerBands().compute(candles, period=20)
    assert result.shape[1] == 3  # (upper, middle, lower)
    assert result.shape[0] == len(closes) - 20 + 1


def test_bollinger_bands_upper_gt_lower():
    closes = [float(100 + i % 10) for i in range(30)]
    candles = make_candles(closes)
    result = BollingerBands().compute(candles, period=20)
    assert np.all(result[:, 0] >= result[:, 2])  # upper >= lower


def test_bollinger_bands_too_few():
    candles = make_candles([100, 101])
    result = BollingerBands().compute(candles, period=20)
    assert result.shape == (0, 3)


# --- ATR ---
def test_atr_length():
    closes = list(range(100, 130))
    highs = [c + 2 for c in closes]
    lows = [c - 2 for c in closes]
    candles = make_candles(closes, highs, lows)
    result = ATR().compute(candles, period=14)
    expected_len = len(candles) - 14 - 1 + 1  # len(tr) = n-1, then rolling mean
    assert len(result) == expected_len


def test_atr_too_few():
    candles = make_candles([100, 101, 102])
    assert len(ATR().compute(candles, period=14)) == 0


# --- SupportResistance ---
def test_support_resistance_returns_values():
    closes = [100, 102, 99, 104, 101, 105, 100, 106, 102, 107]
    candles = make_candles(closes)
    result = SupportResistance().compute(candles)
    assert len(result) > 0


# --- BreakoutDetector ---
def test_breakout_detector_signals_above():
    closes = [100.0] * 20 + [105.0]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    candles = make_candles(closes, highs, lows)
    result = BreakoutDetector().compute(candles, lookback=20)
    assert result[-1] == 1.0


def test_breakout_detector_too_few():
    candles = make_candles([100.0] * 5)
    result = BreakoutDetector().compute(candles, lookback=20)
    assert len(result) == 0


# --- CandlestickPatterns ---
def test_candlestick_doji():
    candles = [
        Candle(datetime(2024, 1, 1), 100, 100, 100, 100, 1000),
        Candle(datetime(2024, 1, 2), 100.0, 105.0, 95.0, 100.4, 1000),  # doji
    ]
    result = CandlestickPatterns().compute(candles)
    assert result[1] == 2  # doji


def test_candlestick_too_few():
    candles = make_candles([100.0])
    result = CandlestickPatterns().compute(candles)
    assert len(result) == 0
