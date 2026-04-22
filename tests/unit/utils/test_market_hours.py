"""Tests for market hours detection utility."""

from datetime import datetime
from zoneinfo import ZoneInfo
from src.utils.market_hours import is_market_open


def test_market_open_during_regular_hours():
    """Tuesday 10:00 AM ET should be open."""
    dt = datetime(2026, 4, 22, 10, 0, tzinfo=ZoneInfo("America/New_York"))
    assert is_market_open(dt) is True


def test_market_closed_before_open():
    """Tuesday 9:00 AM ET should be closed."""
    dt = datetime(2026, 4, 22, 9, 0, tzinfo=ZoneInfo("America/New_York"))
    assert is_market_open(dt) is False


def test_market_closed_after_close():
    """Tuesday 5:00 PM ET should be closed."""
    dt = datetime(2026, 4, 22, 17, 0, tzinfo=ZoneInfo("America/New_York"))
    assert is_market_open(dt) is False


def test_market_closed_weekends():
    """Saturday 10:00 AM ET should be closed."""
    dt = datetime(2026, 4, 19, 10, 0, tzinfo=ZoneInfo("America/New_York"))  # Saturday
    assert is_market_open(dt) is False


def test_market_open_exactly_at_open():
    """Monday 9:30 AM ET should be open."""
    dt = datetime(2026, 4, 20, 9, 30, tzinfo=ZoneInfo("America/New_York"))  # Monday
    assert is_market_open(dt) is True


def test_market_closed_exactly_at_close():
    """Monday 4:00 PM ET should be closed."""
    dt = datetime(2026, 4, 20, 16, 0, 0, tzinfo=ZoneInfo("America/New_York"))
    assert is_market_open(dt) is False


def test_market_open_no_timezone_provided_uses_et():
    """Naive datetime should be treated as ET."""
    dt = datetime(2026, 4, 22, 10, 0)  # No timezone
    # Should convert to ET and be open
    assert is_market_open(dt) is True
