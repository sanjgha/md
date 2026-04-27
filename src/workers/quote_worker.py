"""Background worker for polling realtime quotes from MarketData.app."""

import asyncio
import logging
from datetime import datetime
from typing import Dict

from sqlalchemy.orm import Session

from src.api.watchlists.quote_cache_service import QuoteCacheService
from src.data_provider.base import DataProvider, Quote
from src.data_provider.batch import get_realtime_quotes_batch
from src.db.models import RealtimeQuote, Stock, WatchlistSymbol
from src.utils.market_hours import is_market_open

logger = logging.getLogger(__name__)


class QuoteWorker:
    """Background worker that polls MarketData.app for realtime quotes.

    Runs every 1 minute during regular market hours (Mon-Fri 9:30 AM - 4:00 PM ET).
    Fetches quotes for all unique symbols across all user watchlists.
    Stores results in realtime_quotes table and updates cache.
    """

    def __init__(
        self,
        db_session: Session,
        cache_service: QuoteCacheService,
        provider: DataProvider,
    ):
        """Initialize the worker.

        Args:
            db_session: SQLAlchemy database session
            cache_service: QuoteCacheService instance
            provider: DataProvider instance for fetching quotes
        """
        self.db = db_session
        self.cache = cache_service
        self.provider = provider

    def poll(self) -> int:
        """Poll for quotes and update database/cache if market is open.

        Returns:
            Number of quotes fetched (0 if market closed or error)
        """
        if not is_market_open():
            logger.debug("Market closed, skipping quote poll")
            return 0

        try:
            symbols = self._get_all_symbols()
            if not symbols:
                logger.debug("No symbols in watchlists")
                return 0

            # Fetch quotes from MarketData.app — returns dict[symbol, Quote]
            quotes: Dict[str, Quote] = asyncio.run(
                get_realtime_quotes_batch(self.provider, symbols)
            )

            if not quotes:
                logger.warning("No quotes fetched (all symbols may be invalid)")
                return 0

            # Store in database using symbol-keyed dict (no index alignment assumption)
            self._store_quotes(quotes)

            # Update cache (outside database transaction)
            from src.api.watchlists.schemas import QuoteResponse

            cache_quotes = [
                QuoteResponse(
                    symbol=symbol,
                    last=quote.last,
                    low=quote.low or None,
                    high=quote.high or None,
                    change=quote.change,
                    change_pct=quote.change_pct,
                    source="realtime",
                    date=None,
                    intraday=[],
                )
                for symbol, quote in quotes.items()
            ]
            self.cache.refresh_cache(cache_quotes)

            logger.info("Polled %d quotes", len(quotes))
            return len(quotes)

        except Exception as e:
            # Rollback database if cache update fails
            self.db.rollback()
            logger.error("Error polling quotes: %s", e)
            return 0

    def _get_all_symbols(self) -> list[str]:
        """Get all unique symbols from all user watchlists.

        Returns:
            List of unique stock symbols
        """
        rows = (
            self.db.query(Stock.symbol)
            .join(WatchlistSymbol, Stock.id == WatchlistSymbol.stock_id)
            .distinct()
            .all()
        )
        return [row.symbol for row in rows]

    def _store_quotes(self, quotes: Dict[str, Quote]) -> None:
        """Store quotes in realtime_quotes table.

        Deletes today's existing entries before inserting new ones.

        Args:
            quotes: Dict mapping symbol -> Quote
        """
        symbols = list(quotes.keys())

        # Get stock IDs
        symbol_to_stock = {
            row.symbol: row.id
            for row in self.db.query(Stock.id, Stock.symbol).filter(Stock.symbol.in_(symbols)).all()
        }

        # Delete today's entries for these symbols
        today = datetime.utcnow().date()
        self.db.query(RealtimeQuote).filter(
            RealtimeQuote.stock_id.in_(symbol_to_stock.values()), RealtimeQuote.timestamp >= today
        ).delete()

        # Insert new quotes — symbol-keyed so no index alignment needed
        for symbol, quote in quotes.items():
            if symbol not in symbol_to_stock:
                continue

            self.db.add(
                RealtimeQuote(
                    stock_id=symbol_to_stock[symbol],
                    bid=quote.bid,
                    ask=quote.ask,
                    bid_size=quote.bid_size,
                    ask_size=quote.ask_size,
                    last=quote.last,
                    open=quote.open,
                    high=quote.high or None,
                    low=quote.low or None,
                    close=quote.close,
                    volume=quote.volume,
                    change=quote.change,
                    change_pct=quote.change_pct,
                    week_52_high=quote.week_52_high,
                    week_52_low=quote.week_52_low,
                    status=quote.status,
                    timestamp=quote.timestamp,
                )
            )

        self.db.commit()
