"""Expiry bucket calculation for options chain ingestion."""

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class ExpiryBucket:
    """Target expiry bucket with label and expiry date."""

    label: str  # "current_week" | "next_week" | "monthly"
    expiry: date


def _next_friday(d: date) -> date:
    """Return the next Friday on or after d."""
    days_ahead = 4 - d.weekday()  # Friday is weekday 4
    if days_ahead <= 0:
        days_ahead += 7
    return d + timedelta(days=days_ahead)


def _third_friday(year: int, month: int) -> date:
    """Return the third Friday of the given month."""
    first = date(year, month, 1)
    first_friday = first + timedelta(days=(4 - first.weekday()) % 7)
    return first_friday + timedelta(weeks=2)


def determine_target_expiries(as_of: date) -> list[ExpiryBucket]:
    """Return current_week, next_week, and monthly expiry buckets."""
    current_week_fri = _next_friday(as_of)

    next_week_start = current_week_fri + timedelta(days=3)  # Monday after
    next_week_fri = _next_friday(next_week_start)

    year, month = as_of.year, as_of.month
    monthly = _third_friday(year, month)
    if monthly <= as_of:
        month += 1
        if month > 12:
            month = 1
            year += 1
        monthly = _third_friday(year, month)

    return [
        ExpiryBucket(label="current_week", expiry=current_week_fri),
        ExpiryBucket(label="next_week", expiry=next_week_fri),
        ExpiryBucket(label="monthly", expiry=monthly),
    ]
