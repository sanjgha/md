"""Unit tests for QuoteCacheService."""

import time
from src.api.watchlists.quote_cache_service import QuoteCacheService
from src.api.watchlists.schemas import QuoteResponse


def test_cache_miss_returns_empty():
    """Cache should return empty list when no quotes cached."""
    service = QuoteCacheService()
    result = service.get_quotes(["AAPL", "MSFT"])
    assert result == []


def test_cache_hit_returns_cached_quotes():
    """Cache should return cached quotes if available."""
    service = QuoteCacheService()
    quotes = [
        QuoteResponse(
            symbol="AAPL", last=150.0, change=1.0, change_pct=0.67, source="realtime", date=None
        )
    ]
    service.refresh_cache(quotes)

    result = service.get_quotes(["AAPL"])
    assert len(result) == 1
    assert result[0].symbol == "AAPL"
    assert result[0].last == 150.0


def test_cache_expires_after_ttl():
    """Cache entries should expire after 30 seconds."""
    service = QuoteCacheService()
    quotes = [
        QuoteResponse(
            symbol="AAPL", last=150.0, change=1.0, change_pct=0.67, source="realtime", date=None
        )
    ]
    service.refresh_cache(quotes)

    # Wait for TTL to expire
    time.sleep(31)

    result = service.get_quotes(["AAPL"])
    assert result == []


def test_cache_partial_hit():
    """Cache should return cached quotes and skip uncached symbols."""
    service = QuoteCacheService()
    quotes = [
        QuoteResponse(
            symbol="AAPL", last=150.0, change=1.0, change_pct=0.67, source="realtime", date=None
        )
    ]
    service.refresh_cache(quotes)

    result = service.get_quotes(["AAPL", "MSFT"])
    assert len(result) == 1
    assert result[0].symbol == "AAPL"


def test_refresh_cache_overwrites_old_entries():
    """Refreshing cache should replace existing entries."""
    service = QuoteCacheService()
    old_quotes = [
        QuoteResponse(
            symbol="AAPL", last=150.0, change=1.0, change_pct=0.67, source="realtime", date=None
        )
    ]
    service.refresh_cache(old_quotes)

    new_quotes = [
        QuoteResponse(
            symbol="AAPL", last=155.0, change=6.0, change_pct=4.0, source="realtime", date=None
        )
    ]
    service.refresh_cache(new_quotes)

    result = service.get_quotes(["AAPL"])
    assert result[0].last == 155.0
