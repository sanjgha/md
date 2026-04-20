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
    use the same timestamp object.
    """
    from datetime import datetime, timezone
    from src.options_agent.ivr import compute_and_store_ivr

    bars = synthetic_bars_rising_volatility()
    fixed_time = datetime(2025, 1, 15, 12, 30, 45, tzinfo=timezone.utc)

    # Create a mock session to capture the executed statement
    mock_session = MagicMock()
    captured_stmt = {}

    def capture_execute(stmt):
        # Capture the statement for later inspection
        captured_stmt["stmt"] = stmt
        return None

    mock_session.execute.side_effect = capture_execute

    # Patch datetime.now to return our fixed time
    with patch("src.options_agent.ivr.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_time
        mock_datetime.timezone = timezone

        result = compute_and_store_ivr(
            session=mock_session, symbol="TEST", bars=bars, as_of=date(2025, 1, 15)
        )

        # Verify the function executed and returned a result
        assert "stmt" in captured_stmt, "Statement was not executed"
        assert result.ivr is not None
        assert result.current_hv is not None

        # Verify datetime.now was called exactly once (regression check)
        # Before fix: would be called twice (once in .values(), once in .set_())
        call_count = mock_datetime.now.call_count
        assert call_count == 1, f"Expected 1 call to datetime.now, got {call_count}"

        # Now verify the same timestamp object appears in both INSERT and UPDATE
        stmt = captured_stmt["stmt"]

        # Extract computed_at from INSERT .values()
        insert_computed_at = None
        for col, bindparam in stmt._values.items():
            if col.name == "computed_at":
                insert_computed_at = bindparam.value
                break

        # Extract computed_at from ON CONFLICT UPDATE .set_()
        update_computed_at = None
        pvc = stmt._post_values_clause
        for col_name, val in pvc.update_values_to_set:
            if col_name == "computed_at":
                update_computed_at = val
                break

        # Verify both are present
        assert insert_computed_at is not None, "computed_at not found in INSERT values"
        assert update_computed_at is not None, "computed_at not found in UPDATE set_"

        # Verify they are the SAME object (not just equal values)
        assert (
            insert_computed_at is update_computed_at
        ), f"INSERT and UPDATE use different timestamp objects: {id(insert_computed_at)} vs {id(update_computed_at)}"

        # Verify both have the fixed time value
        assert insert_computed_at == fixed_time
        assert update_computed_at == fixed_time
