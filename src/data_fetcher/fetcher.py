"""DataFetcher: orchestrates bulk upsert sync operations with rate limiting."""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.data_provider.base import DataProvider
from src.data_provider.batch_candles import get_daily_candles_batch, get_intraday_candles_batch
from src.data_provider.bulk_candles_by_day import (
    get_bulk_candles_for_date_range,
)
from src.db.models import (
    DailyCandle,
    EarningsCalendar,
    IntradayCandle,
    RealtimeQuote,
    Stock,
    StockNews,
)

logger = logging.getLogger(__name__)


class DataFetcher:
    """Orchestrates all data syncing operations with bulk upsert and rate limiting."""

    def __init__(
        self,
        provider: DataProvider,
        db: Session,
        rate_limit_delay: float = 0.1,
        enable_earnings_sync: bool = True,
        enable_news_sync: bool = True,
        use_batch: bool = True,
        max_concurrent: int = 10,
    ):
        """Initialize fetcher with provider, DB session, and rate limit delay.

        Args:
            provider: DataProvider instance
            db: SQLAlchemy session
            rate_limit_delay: Seconds to sleep between sequential requests
            enable_earnings_sync: Whether to sync earnings data
            enable_news_sync: Whether to sync news data
            use_batch: Use parallel async batch requests (5x faster)
            max_concurrent: Max concurrent requests when use_batch=True
        """
        self.provider = provider
        self.db = db
        self.rate_limit_delay = rate_limit_delay
        self.enable_earnings_sync = enable_earnings_sync
        self.enable_news_sync = enable_news_sync
        self.use_batch = use_batch
        self.max_concurrent = max_concurrent

    def _bulk_upsert_daily_candles(self, stock_id: int, candles) -> int:
        """Bulk upsert daily candles; re-fetches overwrite existing rows (e.g. post-split adjustment)."""
        if not candles:
            return 0
        rows = [
            {
                "stock_id": stock_id,
                "timestamp": c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in candles
        ]
        insert_stmt = pg_insert(DailyCandle).values(rows)
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=["stock_id", "timestamp"],
            set_={
                "open": insert_stmt.excluded.open,
                "high": insert_stmt.excluded.high,
                "low": insert_stmt.excluded.low,
                "close": insert_stmt.excluded.close,
                "volume": insert_stmt.excluded.volume,
            },
        )
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount  # type: ignore[attr-defined]

    def _bulk_upsert_intraday_candles(self, stock_id: int, resolution: str, candles) -> int:
        """Bulk upsert intraday candles; re-fetches overwrite existing rows."""
        if not candles:
            return 0
        rows = [
            {
                "stock_id": stock_id,
                "resolution": resolution,
                "timestamp": c.timestamp,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in candles
        ]
        insert_stmt = pg_insert(IntradayCandle).values(rows)
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=["stock_id", "resolution", "timestamp"],
            set_={
                "open": insert_stmt.excluded.open,
                "high": insert_stmt.excluded.high,
                "low": insert_stmt.excluded.low,
                "close": insert_stmt.excluded.close,
                "volume": insert_stmt.excluded.volume,
            },
        )
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount  # type: ignore[attr-defined]

    def _detect_corporate_action(self, symbol: str, candles) -> bool:
        """Return True on the first overnight gap that exceeds 35%, logging a warning.

        Threshold catches 2:1 forward splits (50% drop), 1:10 reverse splits (900% rise),
        and anything in between. Genuine earnings gaps rarely exceed 35% on daily data.
        """
        sorted_c = sorted(candles, key=lambda c: c.timestamp)
        for prev, curr in zip(sorted_c, sorted_c[1:]):
            if prev.close <= 0:
                continue
            gap = abs(curr.open / prev.close - 1)
            if gap > 0.35:
                logger.warning(
                    "Possible corporate action %s: prev_close=%.2f curr_open=%.2f gap=%.1f%%",
                    symbol,
                    prev.close,
                    curr.open,
                    gap * 100,
                )
                return True
        return False

    def sync_daily(
        self,
        symbols: Optional[List[str]] = None,
        days_back: int = 365,
    ) -> None:
        """Sync daily candles for all (or specified) stocks.

        Uses parallel async batch requests when use_batch=True (default),
        otherwise falls back to sequential fetching.
        """
        stock_map = {str(s.symbol): int(s.id) for s in self.db.query(Stock).all()}
        if symbols is None:
            symbols = list(stock_map.keys())

        to_date = datetime.utcnow()
        from_date = to_date - timedelta(days=days_back)

        if self.use_batch:
            self._sync_daily_batch(symbols, stock_map, from_date, to_date)
        else:
            self._sync_daily_sequential(symbols, stock_map, from_date, to_date)

    def _sync_daily_batch(
        self,
        symbols: List[str],
        stock_map: dict,
        from_date: datetime,
        to_date: datetime,
    ) -> None:
        """Sync daily candles using parallel async batch requests."""
        logger.info(
            f"Starting batch sync for {len(symbols)} symbols (concurrency={self.max_concurrent})"
        )

        try:
            # Fetch all candles in parallel
            all_candles = asyncio.run(
                get_daily_candles_batch(
                    self.provider,
                    symbols,
                    from_date,
                    to_date,
                    max_concurrent=self.max_concurrent,
                )
            )
        except ValueError as e:
            if "base_url and api_token attributes" in str(e):
                logger.info(
                    "Provider does not support batch fetching (missing base_url/api_token), "
                    "falling back to sequential mode"
                )
                self._sync_daily_sequential(symbols, stock_map, from_date, to_date)
                return
            raise

        # Upsert each symbol's candles
        total_inserted = 0
        for symbol, candles in all_candles.items():
            stock_id = stock_map.get(symbol)
            if not stock_id:
                logger.warning(f"Stock {symbol} not found in DB — skipping")
                continue

            self._detect_corporate_action(symbol, candles)
            inserted = self._bulk_upsert_daily_candles(stock_id, candles)
            total_inserted += inserted
            logger.debug(f"sync_daily {symbol}: {inserted} rows")

        logger.info(
            f"Batch sync complete: {total_inserted} total rows for {len(all_candles)} symbols"
        )

    def _sync_daily_sequential(
        self,
        symbols: List[str],
        stock_map: dict,
        from_date: datetime,
        to_date: datetime,
    ) -> None:
        """Sync daily candles sequentially (legacy method)."""
        for symbol in symbols:
            stock_id = stock_map.get(symbol)
            if not stock_id:
                logger.warning(f"Stock {symbol} not found in DB — skipping")
                continue
            try:
                candles = self.provider.get_daily_candles(
                    symbol=symbol, from_date=from_date, to_date=to_date
                )
                self._detect_corporate_action(symbol, candles)
                inserted = self._bulk_upsert_daily_candles(stock_id, candles)
                logger.info(f"sync_daily {symbol}: {inserted} new rows")
                time.sleep(self.rate_limit_delay)
            except Exception as e:
                logger.error(f"Failed to sync daily {symbol}: {e}")
                self.db.rollback()

    def sync_intraday(
        self,
        symbols: Optional[List[str]] = None,
        resolutions: Optional[List[str]] = None,
        days_back: int = 7,
    ) -> None:
        """Sync intraday candles for 5m, 15m, 1h resolutions.

        Uses parallel async batch requests when use_batch=True (default),
        otherwise falls back to sequential fetching.
        """
        if resolutions is None:
            resolutions = ["5m", "15m", "1h"]
        stock_map = {str(s.symbol): int(s.id) for s in self.db.query(Stock).all()}
        if symbols is None:
            symbols = list(stock_map.keys())

        to_date = datetime.utcnow()
        from_date = to_date - timedelta(days=days_back)

        if self.use_batch:
            self._sync_intraday_batch(symbols, stock_map, from_date, to_date, resolutions)
        else:
            self._sync_intraday_sequential(symbols, stock_map, from_date, to_date, resolutions)

    def _sync_intraday_batch(
        self,
        symbols: List[str],
        stock_map: dict,
        from_date: datetime,
        to_date: datetime,
        resolutions: List[str],
    ) -> None:
        """Sync intraday candles using parallel async batch requests."""
        logger.info(
            f"Starting batch intraday sync for {len(symbols)} symbols, {len(resolutions)} resolutions"
        )

        try:
            total_inserted = 0
            for resolution in resolutions:
                logger.info(f"Fetching {resolution} candles...")
                all_candles = asyncio.run(
                    get_intraday_candles_batch(
                        self.provider,
                        symbols,
                        resolution,
                        from_date,
                        to_date,
                        max_concurrent=self.max_concurrent,
                    )
                )

                for symbol, candles in all_candles.items():
                    stock_id = stock_map.get(symbol)
                    if not stock_id:
                        continue
                    inserted = self._bulk_upsert_intraday_candles(stock_id, resolution, candles)
                    total_inserted += inserted
                    logger.debug(f"sync_intraday {symbol} {resolution}: {inserted} rows")

            logger.info(f"Batch intraday sync complete: {total_inserted} total rows")

        except ValueError as e:
            if "base_url and api_token attributes" in str(e):
                logger.info(
                    "Provider does not support batch fetching (missing base_url/api_token), "
                    "falling back to sequential mode"
                )
                self._sync_intraday_sequential(symbols, stock_map, from_date, to_date, resolutions)
                return
            raise

    def _sync_intraday_sequential(
        self,
        symbols: List[str],
        stock_map: dict,
        from_date: datetime,
        to_date: datetime,
        resolutions: List[str],
    ) -> None:
        """Sync intraday candles sequentially (legacy method)."""
        for symbol in symbols:
            stock_id = stock_map.get(symbol)
            if not stock_id:
                continue
            for resolution in resolutions:
                try:
                    candles = self.provider.get_intraday_candles(
                        symbol=symbol,
                        resolution=resolution,
                        from_date=from_date,
                        to_date=to_date,
                    )
                    inserted = self._bulk_upsert_intraday_candles(stock_id, resolution, candles)
                    logger.info(f"sync_intraday {symbol} {resolution}: {inserted} new rows")
                except Exception as e:
                    logger.error(f"Failed to sync intraday {symbol} {resolution}: {e}")
                    self.db.rollback()
            time.sleep(self.rate_limit_delay)

    def sync_daily_incremental(
        self,
        symbols: Optional[List[str]] = None,
        days_back: int = 1,
        force_full_refresh: bool = False,
    ) -> None:
        """Sync only the latest N daily candles using bulk endpoint.

        This is optimal for daily EOD jobs where you only need recent data.
        Uses /stocks/bulkcandles/D/ which returns all symbols for a specific date.

        GAP HANDLING: Automatically detects gaps by checking the latest candle
        timestamp in the database for each symbol. Fetches from the day after
        the latest candle to current, ensuring no gaps even if sync skips days.

        IMPORTANT: This does NOT detect corporate actions (splits) in historical data.
        Use force_full_refresh=True or run periodic full refreshes to catch restatements.

        Args:
            symbols: List of symbols to sync (default: all)
            days_back: Number of recent days to fetch (default: 1 = today only)
                       Only used if symbol has no existing data.
            force_full_refresh: If True, skip bulk and do full fetch (for corporate action detection)

        API Calls: N days = N calls (vs 500 calls with standard endpoint)

        Recommendation: Run with force_full_refresh=True weekly to catch corporate actions.
        """
        from sqlalchemy import func

        stock_map = {str(s.symbol): int(s.id) for s in self.db.query(Stock).all()}
        if symbols is None:
            symbols = list(stock_map.keys())

        # Force full refresh periodically for corporate action detection
        if force_full_refresh:
            logger.info("Force full refresh requested - using standard endpoint")
            self.sync_daily(symbols=symbols, days_back=max(365, days_back))
            return

        # Check if provider supports bulk candles
        base_url = getattr(self.provider, "base_url", None)
        api_token = getattr(self.provider, "api_token", None)

        if not base_url or not api_token:
            logger.info(
                "Provider does not support bulk candles (missing base_url/api_token), "
                "falling back to standard sync"
            )
            self.sync_daily(symbols=symbols, days_back=days_back)
            return

        # Find the latest candle timestamp for each stock to detect gaps
        latest_candle_query = (
            self.db.query(DailyCandle.stock_id, func.max(DailyCandle.timestamp).label("latest_ts"))
            .filter(DailyCandle.stock_id.in_(stock_map.values()))
            .group_by(DailyCandle.stock_id)
        )
        latest_by_stock = {stock_id: latest_ts for stock_id, latest_ts in latest_candle_query.all()}

        # Determine date range to fetch for each stock
        to_date = datetime.utcnow()
        symbol_date_ranges: Dict[str, Tuple[datetime, datetime]] = {}

        for symbol, stock_id in stock_map.items():
            if stock_id in latest_by_stock:
                # Has existing data - fetch from day after latest candle
                from_date = latest_by_stock[stock_id] + timedelta(days=1)
                # Don't fetch future dates
                if from_date > to_date:
                    # Data is already up to date
                    symbol_date_ranges[symbol] = None
                    continue
                symbol_date_ranges[symbol] = (from_date, to_date)
            else:
                # No existing data - fetch last N days
                from_date = to_date - timedelta(days=days_back - 1)
                symbol_date_ranges[symbol] = (from_date, to_date)

        # Group symbols by their date ranges to minimize API calls
        range_to_symbols: Dict[Tuple[datetime, datetime], List[str]] = {}
        symbols_needing_sync: List[str] = []

        for symbol, date_range in symbol_date_ranges.items():
            if date_range is None:
                continue  # Already up to date
            symbols_needing_sync.append(symbol)
            range_to_symbols.setdefault(date_range, []).append(symbol)

        if not symbols_needing_sync:
            logger.info("All symbols up to date - no incremental sync needed")
            return

        logger.info(
            f"Starting gap-aware incremental bulk sync for {len(symbols_needing_sync)} symbols"
        )
        logger.info(f"Date ranges to fetch: {len(range_to_symbols)} unique range(s)")

        # Fetch each unique date range once
        total_inserted = 0
        for (from_date, to_date), symbols_in_range in range_to_symbols.items():
            num_days = (to_date - from_date).days + 1
            logger.info(
                f"Fetching {num_days} day(s) from {from_date.date()} to {to_date.date()} "
                f"for {len(symbols_in_range)} symbols"
            )

            all_candles = get_bulk_candles_for_date_range(
                api_token, base_url, from_date, to_date, symbols_in_range
            )

            for symbol, candles in all_candles.items():
                stock_id = stock_map.get(symbol)
                if not stock_id:
                    continue
                inserted = self._bulk_upsert_daily_candles(stock_id, candles)
                total_inserted += inserted
                logger.debug(f"sync_daily_incremental {symbol}: {inserted} rows")

        logger.info(
            f"Incremental bulk sync complete: {total_inserted} total rows for {len(symbols_needing_sync)} symbols"
        )
        logger.info(
            "NOTE: Corporate action detection skipped. Run with force_full_refresh=True "
            "periodically (recommended: weekly) to catch stock splits and restatements."
        )

    def sync_daily_smart(self, symbols: Optional[List[str]] = None) -> str:
        """Smart sync that automatically chooses full refresh or incremental based on day of week.

        Strategy:
        - Saturday: Full refresh (365 days) - detects all corporate actions
        - Other days: Incremental bulk sync - fills gaps efficiently

        This ensures any stock splits or price restatements are caught within a week
        while saving 99%+ API calls on non-Saturday days.

        Args:
            symbols: List of symbols to sync (default: all)

        Returns:
            str: The sync type performed ("full" or "incremental")
        """
        from datetime import date as date_type

        today = date_type.today()
        day_of_week = today.weekday()  # 0=Monday, 5=Saturday, 6=Sunday

        # Saturday = 5, do full refresh
        if day_of_week == 5:
            logger.info(
                f"Saturday {today.strftime('%Y-%m-%d')} - running FULL refresh "
                "for corporate action detection"
            )
            self.sync_daily(symbols=symbols, days_back=365)
            return "full"
        else:
            days_until_saturday = 5 - day_of_week if day_of_week < 5 else (5 + 7 - day_of_week)
            logger.info(
                f"{today.strftime('%A')} - running INCREMENTAL sync "
                f"(next full refresh: Saturday in {days_until_saturday} day(s))"
            )
            self.sync_daily_incremental(symbols=symbols, days_back=1)
            return "incremental"

    def sync_news(
        self,
        symbols: Optional[List[str]] = None,
        countback: int = 50,
    ) -> None:
        """Sync news articles for all stocks."""
        if not self.enable_news_sync:
            logger.info("News sync disabled via config - skipping")
            return

        stock_map = {str(s.symbol): int(s.id) for s in self.db.query(Stock).all()}
        if symbols is None:
            symbols = list(stock_map.keys())

        for symbol in symbols:
            stock_id = stock_map.get(symbol)
            if not stock_id:
                continue
            try:
                articles = self.provider.get_news(symbol=symbol, countback=countback)
                for article in articles:
                    stmt = (
                        pg_insert(StockNews)
                        .values(
                            stock_id=stock_id,
                            headline=article.headline,
                            content=article.content,
                            source=article.source,
                            publication_date=article.publication_date,
                        )
                        .on_conflict_do_nothing(
                            index_elements=["stock_id", "source", "publication_date"]
                        )
                    )
                    self.db.execute(stmt)
                self.db.commit()
                time.sleep(self.rate_limit_delay)
            except Exception as e:
                logger.error(f"Failed to sync news {symbol}: {e}")
                self.db.rollback()

    def sync_earnings(self, symbols: Optional[List[str]] = None) -> None:
        """Sync earnings calendar."""
        if not self.enable_earnings_sync:
            logger.info("Earnings sync disabled via config - skipping")
            return

        stock_map = {str(s.symbol): int(s.id) for s in self.db.query(Stock).all()}
        if symbols is None:
            symbols = list(stock_map.keys())

        for symbol in symbols:
            stock_id = stock_map.get(symbol)
            if not stock_id:
                continue
            try:
                earnings = self.provider.get_earnings_history(symbol=symbol)
                rows = [
                    {
                        "stock_id": stock_id,
                        "fiscal_year": e.fiscal_year,
                        "fiscal_quarter": e.fiscal_quarter,
                        "earnings_date": e.earnings_date,
                        "report_date": e.report_date,
                        "report_time": e.report_time,
                        "currency": e.currency,
                        "reported_eps": e.reported_eps,
                        "estimated_eps": e.estimated_eps,
                    }
                    for e in earnings
                ]
                if rows:
                    stmt = (
                        pg_insert(EarningsCalendar)
                        .values(rows)
                        .on_conflict_do_nothing(index_elements=["stock_id", "earnings_date"])
                    )
                    self.db.execute(stmt)
                    self.db.commit()
                time.sleep(self.rate_limit_delay)
            except Exception as e:
                logger.error(f"Failed to sync earnings {symbol}: {e}")
                self.db.rollback()

    def cleanup_old_intraday(self, days_retention: int = 7) -> None:
        """Delete intraday candles older than retention period."""
        cutoff = datetime.utcnow() - timedelta(days=days_retention)
        deleted = self.db.query(IntradayCandle).filter(IntradayCandle.created_at < cutoff).delete()
        self.db.commit()
        logger.info(f"Deleted {deleted} old intraday candles")

    def cleanup_old_quotes(self, days_retention: int = 7) -> None:
        """Delete realtime quotes older than retention period."""
        cutoff = datetime.utcnow() - timedelta(days=days_retention)
        deleted = self.db.query(RealtimeQuote).filter(RealtimeQuote.created_at < cutoff).delete()
        self.db.commit()
        logger.info(f"Deleted {deleted} old realtime quotes")
