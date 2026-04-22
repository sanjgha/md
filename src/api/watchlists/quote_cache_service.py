"""In-memory cache for realtime quotes with 30-second TTL."""

import time
from dataclasses import dataclass
from typing import List

from src.api.watchlists.schemas import QuoteResponse


@dataclass
class CachedQuote:
    """A cached quote with expiration timestamp."""

    quote: QuoteResponse
    expires_at: float


class QuoteCacheService:
    """In-memory cache for realtime quotes.

    Cache entries expire after 30 seconds. The refresh_cache() method
    replaces all existing entries with new data.
    """

    CACHE_TTL_SECONDS = 30

    def __init__(self):
        """Initialize empty cache."""
        self._cache: dict[str, CachedQuote] = {}

    def get_quotes(self, symbols: List[str]) -> List[QuoteResponse]:
        """Get cached quotes for symbols, filtering expired entries.

        Args:
            symbols: List of stock symbols to retrieve

        Returns:
            List of cached QuoteResponse objects (only non-expired)
        """
        now = time.time()
        result = []

        for symbol in symbols:
            cached = self._cache.get(symbol)
            if cached and cached.expires_at > now:
                result.append(cached.quote)

        return result

    def refresh_cache(self, quotes: List[QuoteResponse]) -> None:
        """Replace all cache entries with new quotes.

        Sets expiration timestamp to now + 30 seconds.

        Args:
            quotes: New quotes to cache
        """
        now = time.time()
        expires_at = now + self.CACHE_TTL_SECONDS

        # Clear old cache and add new entries
        self._cache.clear()
        for quote in quotes:
            self._cache[quote.symbol] = CachedQuote(quote=quote, expires_at=expires_at)
