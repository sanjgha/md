import pytest
from datetime import date
from unittest.mock import patch, MagicMock
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


def test_compute_and_store_ivr_uses_same_timestamp_for_insert_and_update():
    """Verify that insert and update paths use the same computed_at timestamp.

    This test ensures that multiple upserts of the same symbol/date/basis
    produce rows with identical computed_at values (deterministic behavior).
    The test mocks datetime.now to verify both .values() and .set_() calls
    use the same timestamp.
    """
    from datetime import datetime, timezone
    from src.options_agent.ivr import compute_and_store_ivr

    bars = synthetic_bars_rising_volatility()
    fixed_time = datetime(2025, 1, 15, 12, 30, 45, tzinfo=timezone.utc)

    # Create a mock session to capture the executed statement
    mock_session = MagicMock()
    executed_values = {}

    def capture_execute(stmt):
        # For this test, we just want to verify the function executes without error
        executed_values["called"] = True

    mock_session.execute.side_effect = capture_execute

    # Patch datetime.now to return our fixed time
    with patch("src.options_agent.ivr.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_time
        mock_datetime.timezone = timezone

        result = compute_and_store_ivr(
            session=mock_session, symbol="TEST", bars=bars, as_of=date(2025, 1, 15)
        )

        # Verify the function executed and returned a result
        assert executed_values.get("called") is True
        assert result.ivr is not None
        assert result.current_hv is not None

        # Verify datetime.now was called (should be called once after the fix)
        # Each call to datetime.now(timezone.utc) should result in the fixed time
        call_count = mock_datetime.now.call_count
        # After fix: should be called exactly once
        # Before fix: would be called twice (once in .values(), once in .set_())
        assert call_count == 1, f"Expected 1 call to datetime.now, got {call_count}"
