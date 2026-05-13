"""Unit tests for Mansfield Relative Strength helper."""

from datetime import datetime, timedelta
import numpy as np

from src.data_provider.base import Candle
from src.scanner.indicators.relative_strength import compute_mansfield_rs


def _make_candles(closes: list[float], start: datetime | None = None) -> list[Candle]:
    """Build a list of Candles with sequential daily timestamps; OHLV are stubs."""
    start = start or datetime(2025, 1, 1)
    return [
        Candle(
            timestamp=start + timedelta(days=i),
            open=c,
            high=c,
            low=c,
            close=c,
            volume=1_000_000,
        )
        for i, c in enumerate(closes)
    ]


def test_mansfield_positive_when_stock_outperforms():
    # Stock rises 30%, benchmark rises 10% over 300 bars; ratio is rising.
    n = 300
    stock = _make_candles(list(np.linspace(100, 130, n)))
    bench = _make_candles(list(np.linspace(100, 110, n)))
    result = compute_mansfield_rs(stock, bench, sma_period=260, slope_lookback=21)
    assert result is not None
    assert result["mansfield"] > 0
    assert result["rs_slope_ok"] is True


def test_mansfield_zero_when_perfectly_correlated():
    n = 300
    closes = list(np.linspace(100, 150, n))
    stock = _make_candles(closes)
    bench = _make_candles(closes)
    result = compute_mansfield_rs(stock, bench, sma_period=260, slope_lookback=21)
    assert result is not None
    # RS line is constant (100); Mansfield should be ~0 (within float tolerance).
    assert abs(result["mansfield"]) < 1e-6
    assert result["rs_slope_ok"] is False  # constant line is not rising


def test_mansfield_negative_when_underperforming():
    n = 300
    stock = _make_candles(list(np.linspace(100, 105, n)))  # +5%
    bench = _make_candles(list(np.linspace(100, 140, n)))  # +40%
    result = compute_mansfield_rs(stock, bench, sma_period=260, slope_lookback=21)
    assert result is not None
    assert result["mansfield"] < 0
    assert result["rs_slope_ok"] is False


def test_slope_ok_true_when_rs_rising_recently():
    # Stock flat for long stretch, then sprints in the final ~30 bars — slope rising.
    n = 300
    stock_closes = [100.0] * (n - 30) + list(np.linspace(100, 130, 30))
    bench_closes = [100.0] * n
    stock = _make_candles(stock_closes)
    bench = _make_candles(bench_closes)
    result = compute_mansfield_rs(stock, bench, sma_period=260, slope_lookback=21)
    assert result is not None
    assert result["rs_slope_ok"] is True


def test_slope_ok_false_when_rs_flat_recently():
    # Stock outperformed earlier, flat in the last 30 bars.
    n = 300
    stock_closes = list(np.linspace(100, 130, n - 30)) + [130.0] * 30
    bench_closes = [100.0] * n
    stock = _make_candles(stock_closes)
    bench = _make_candles(bench_closes)
    result = compute_mansfield_rs(stock, bench, sma_period=260, slope_lookback=21)
    assert result is not None
    assert result["rs_slope_ok"] is False


def test_returns_none_when_insufficient_aligned_bars():
    stock = _make_candles([100.0] * 100)
    bench = _make_candles([100.0] * 100)
    result = compute_mansfield_rs(stock, bench, sma_period=260, slope_lookback=21)
    assert result is None


def test_aligns_by_timestamp_inner_join():
    # Stock has dates Jan 1-300; benchmark skips Jan 5 and Jan 6 → aligned should be 298.
    stock = _make_candles(list(np.linspace(100, 130, 300)))
    bench_full = _make_candles(list(np.linspace(100, 110, 300)))
    bench = [c for c in bench_full if c.timestamp.day not in (5, 6) or c.timestamp.month != 1]
    result = compute_mansfield_rs(stock, bench, sma_period=260, slope_lookback=21)
    assert result is not None
    # rs_line length equals number of aligned bars (298).
    assert len(result["rs_line"]) == 298


def test_returns_none_on_nan_input():
    stock_closes = [100.0] * 300
    stock_closes[-1] = float("nan")
    stock = _make_candles(stock_closes)
    bench = _make_candles([100.0] * 300)
    result = compute_mansfield_rs(stock, bench, sma_period=260, slope_lookback=21)
    assert result is None


def test_returns_expected_keys():
    n = 300
    stock = _make_candles(list(np.linspace(100, 130, n)))
    bench = _make_candles(list(np.linspace(100, 110, n)))
    result = compute_mansfield_rs(stock, bench, sma_period=260, slope_lookback=21)
    assert set(result.keys()) == {
        "rs_line",
        "rs_sma",
        "rs_today",
        "rs_sma_today",
        "mansfield",
        "rs_slope_ok",
    }
