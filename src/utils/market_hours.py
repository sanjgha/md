"""Market hours detection utility for US equity markets."""

from datetime import datetime
from zoneinfo import ZoneInfo


ET = ZoneInfo("America/New_York")


def is_market_open(dt: datetime | None = None) -> bool:
    """Check if US market is open (Mon-Fri 9:30 AM - 4:00 PM ET).

    Args:
        dt: Datetime to check. If naive, treats as ET. Defaults to now.

    Returns:
        True if market is open, False otherwise.
    """
    if dt is None:
        dt = datetime.now(ET)
    elif dt.tzinfo is None:
        # Naive datetime: assume ET
        dt = dt.replace(tzinfo=ET)
    else:
        # Aware datetime: convert to ET
        dt = dt.astimezone(ET)

    # Weekends (0=Sunday, 6=Saturday)
    if dt.weekday() >= 5:
        return False

    # Before 9:30 AM or after 4:00 PM
    if dt.hour < 9 or dt.hour >= 16:
        return False

    # Between 9:00-9:30 AM
    if dt.hour == 9 and dt.minute < 30:
        return False

    return True
