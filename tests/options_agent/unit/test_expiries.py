"""Unit tests for expiry bucket calculation."""

from datetime import date

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
