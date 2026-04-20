import pytest
from tests.options_agent.conftest import (
    synthetic_bars_rising_volatility,
    synthetic_bars_falling_volatility,
    _make_bars,
)


def test_ivr_returns_percentile_in_range():
    from src.options_agent.ivr import compute_ivr_from_hv

    bars = synthetic_bars_rising_volatility()
    result = compute_ivr_from_hv(bars, window=20, lookback=252)
    assert 0 <= result.ivr <= 100
    assert result.calculation_basis == "hv_proxy"


def test_ivr_at_current_high_is_100():
    from src.options_agent.ivr import compute_ivr_from_hv

    bars = synthetic_bars_rising_volatility()
    result = compute_ivr_from_hv(bars, window=20, lookback=252)
    assert result.ivr == pytest.approx(100.0, abs=1.0)


def test_ivr_at_current_low_is_0():
    from src.options_agent.ivr import compute_ivr_from_hv

    bars = synthetic_bars_falling_volatility()
    result = compute_ivr_from_hv(bars, window=20, lookback=252)
    assert result.ivr == pytest.approx(0.0, abs=1.0)


def test_ivr_insufficient_history_raises():
    from src.options_agent.ivr import compute_ivr_from_hv, InsufficientHistoryError

    bars = _make_bars([100.0] * 50)
    with pytest.raises(InsufficientHistoryError):
        compute_ivr_from_hv(bars, window=20, lookback=252)


def test_ivr_result_fields():
    from src.options_agent.ivr import compute_ivr_from_hv

    bars = synthetic_bars_rising_volatility()
    result = compute_ivr_from_hv(bars, window=20, lookback=252)
    assert result.current_hv > 0
    assert result.hv_min >= 0
    assert result.hv_max >= result.hv_min
    assert result.as_of is not None
