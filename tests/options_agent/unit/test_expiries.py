"""Unit tests for expiry bucket calculation."""

from datetime import date

import pytest
from freezegun import freeze_time


@freeze_time("2026-04-20")  # Monday
def test_expiries_from_monday():
    from src.options_agent.data.expiries import determine_target_expiries

    buckets = determine_target_expiries(as_of=date(2026, 4, 20))
    assert len(buckets) == 3
    assert buckets[0].label == "current_week"
    assert buckets[1].label == "next_week"
    assert buckets[2].label == "monthly"
    # current week friday
    assert buckets[0].expiry == date(2026, 4, 24)
    # next week friday
    assert buckets[1].expiry == date(2026, 5, 1)


@freeze_time("2026-04-23")  # Thursday — current week is imminent
def test_expiries_from_thursday_skips_current_week():
    from src.options_agent.data.expiries import determine_target_expiries

    buckets = determine_target_expiries(as_of=date(2026, 4, 23))
    # On Thursday, current week expiry is tomorrow — still valid
    assert buckets[0].label == "current_week"
    assert buckets[0].expiry == date(2026, 4, 24)


def test_monthly_is_third_friday():
    from src.options_agent.data.expiries import determine_target_expiries

    # May 2026: 3rd Friday is May 15
    buckets = determine_target_expiries(as_of=date(2026, 4, 20))
    monthly = next(b for b in buckets if b.label == "monthly")
    assert monthly.expiry == date(2026, 5, 15)


@pytest.mark.parametrize(
    "as_of_date,expected_monthly,description",
    [
        # December → January year rollover (after Dec's 3rd Friday)
        (date(2025, 12, 20), date(2026, 1, 16), "Dec 2025 → Jan 2026 year rollover"),
        # Month where 1st falls on Saturday (so Aug 3rd Friday is 21st)
        (date(2026, 8, 1), date(2026, 8, 21), "First of month is Saturday"),
        # When as_of equals this month's third Friday, must roll to next month
        (date(2026, 4, 17), date(2026, 5, 15), "as_on_expiry rolls to next month"),
    ],
)
def test_monthly_expiry_edge_cases(as_of_date, expected_monthly, description):
    """Test edge cases: year rollover, first-of-month Saturday, as_on_expiry."""
    from src.options_agent.data.expiries import determine_target_expiries

    buckets = determine_target_expiries(as_of=as_of_date)
    monthly = next(b for b in buckets if b.label == "monthly")
    assert monthly.expiry == expected_monthly, f"Failed: {description}"
