"""Tests for SixMonthHighScanner."""

from datetime import datetime, timedelta
from src.scanner.scanners.six_month_high import SixMonthHighScanner
from src.scanner.context import ScanContext
from src.scanner.indicators.cache import IndicatorCache
from src.scanner.indicators.rolling_max import RollingMax
from src.data_provider.base import Candle


def make_scan_context(stock_id=1, symbol="AAPL", closes=None):
    """Create a ScanContext with daily candles."""
    if closes is None:
        closes = [100.0] * 131

    base = datetime(2024, 1, 1)
    candles = [
        Candle(base + timedelta(days=i), c, c + 1, c - 1, c, 1000) for i, c in enumerate(closes)
    ]

    indicators = {"rolling_max": RollingMax()}
    return ScanContext(
        stock_id=stock_id,
        symbol=symbol,
        daily_candles=candles,
        intraday_candles={},
        indicator_cache=IndicatorCache(indicators),
    )


def test_six_month_high_scanner_returns_list():
    """Scanner should return a list (possibly empty)."""
    context = make_scan_context()
    scanner = SixMonthHighScanner()
    results = scanner.scan(context)
    assert isinstance(results, list)


def test_six_month_high_insufficient_candles():
    """Scanner should return empty list with fewer than 131 candles."""
    context = make_scan_context(closes=[100.0] * 100)
    scanner = SixMonthHighScanner()
    results = scanner.scan(context)
    assert results == []


def test_six_month_high_no_match():
    """Scanner should return empty when no new 6-month high in last 5 days."""
    # Candles 0-124: Various prices up to 200
    # Candles 125-130: All below 200 (no new high)
    closes = [100.0 + i for i in range(125)]  # Ends at 224
    closes.extend([210.0, 212.0, 215.0, 218.0, 220.0, 222.0])  # All below 224

    context = make_scan_context(closes=closes)
    scanner = SixMonthHighScanner()
    results = scanner.scan(context)
    assert results == []


def test_six_month_high_match_today():
    """Scanner should detect new 6-month high today (index -1)."""
    # Candles 0-124: Various prices, max in first 126 = 200
    # Candle 130 (today): Close at 205, breaking 6-month high
    closes = [150.0 + (i % 50) for i in range(125)]  # Oscillates 150-199
    closes.extend([195.0, 196.0, 197.0, 198.0, 199.0, 205.0])  # Last is new high

    context = make_scan_context(closes=closes)
    scanner = SixMonthHighScanner()
    results = scanner.scan(context)

    assert len(results) == 1
    assert results[0].stock_id == 1
    assert results[0].scanner_name == "six_month_high"
    assert results[0].metadata["current_close"] == 205.0
    assert results[0].metadata["days_ago"] == 0


def test_six_month_high_match_3_days_ago():
    """Scanner should detect new 6-month high 3 days ago."""
    # Build 131 candles where 6-month high is broken 3 days ago
    closes = [150.0 + (i % 50) for i in range(125)]  # Oscillates 150-199
    # Last 6 candles: 3 days ago (index -3) breaks the high
    closes.extend([195.0, 196.0, 205.0, 198.0, 197.0, 196.0])

    context = make_scan_context(closes=closes)
    scanner = SixMonthHighScanner()
    results = scanner.scan(context)

    assert len(results) == 1
    assert results[0].metadata["current_close"] == 205.0
    assert results[0].metadata["days_ago"] == 3


def test_six_month_high_multiple_matches_returns_most_recent():
    """Scanner should return only most recent when multiple new highs."""
    # Multiple new highs in 5-day window
    closes = [150.0 + (i % 50) for i in range(125)]  # Max ~199
    # Last 5: break high at -4 (202), break again at -1 (205) → should return -1
    closes.extend([195.0, 202.0, 200.0, 201.0, 203.0, 205.0])

    context = make_scan_context(closes=closes)
    scanner = SixMonthHighScanner()
    results = scanner.scan(context)

    assert len(results) == 1
    assert results[0].metadata["current_close"] == 205.0
    assert results[0].metadata["days_ago"] == 0


def test_six_month_high_exactly_131_candles():
    """Scanner should work with exactly 131 candles (boundary case)."""
    closes = [150.0 + (i % 50) for i in range(125)]
    closes.extend([195.0, 196.0, 197.0, 198.0, 199.0, 205.0])

    context = make_scan_context(closes=closes)
    scanner = SixMonthHighScanner()
    results = scanner.scan(context)

    assert len(results) == 1


def test_six_month_high_metadata_fields():
    """Scanner should include all required metadata fields."""
    closes = [150.0 + (i % 50) for i in range(125)]
    closes.extend([195.0, 196.0, 205.0, 198.0, 197.0, 196.0])

    context = make_scan_context(closes=closes)
    scanner = SixMonthHighScanner()
    results = scanner.scan(context)

    assert len(results) == 1
    metadata = results[0].metadata
    assert "six_month_high" in metadata
    assert "current_close" in metadata
    assert "days_ago" in metadata
    assert "high_date" in metadata
    assert isinstance(metadata["six_month_high"], float)
    assert isinstance(metadata["current_close"], float)
    assert isinstance(metadata["days_ago"], int)


def test_six_month_high_declining_price():
    """Scanner should return empty for declining price series."""
    closes = [200.0 - i * 0.5 for i in range(131)]  # Steadily declining

    context = make_scan_context(closes=closes)
    scanner = SixMonthHighScanner()
    results = scanner.scan(context)

    assert results == []
