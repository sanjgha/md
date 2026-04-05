"""DataFetcher: orchestrates bulk upsert sync operations with rate limiting."""

import logging
import time
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.data_provider.base import DataProvider
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
    ):
        """Initialize fetcher with provider, DB session, and rate limit delay."""
        self.provider = provider
        self.db = db
        self.rate_limit_delay = rate_limit_delay

    def _bulk_upsert_daily_candles(self, stock_id: int, candles) -> int:
        """Bulk insert daily candles using ON CONFLICT DO NOTHING."""
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
        stmt = (
            pg_insert(DailyCandle)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["stock_id", "timestamp"])
        )
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount

    def _bulk_upsert_intraday_candles(self, stock_id: int, resolution: str, candles) -> int:
        """Bulk insert intraday candles using ON CONFLICT DO NOTHING."""
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
        stmt = (
            pg_insert(IntradayCandle)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["stock_id", "resolution", "timestamp"])
        )
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount

    def sync_daily(
        self,
        symbols: Optional[List[str]] = None,
        days_back: int = 365,
    ) -> None:
        """Sync daily candles for all (or specified) stocks."""
        if symbols is None:
            symbols = [s.symbol for s in self.db.query(Stock).all()]

        to_date = datetime.utcnow()
        from_date = to_date - timedelta(days=days_back)

        for symbol in symbols:
            stock = self.db.query(Stock).filter_by(symbol=symbol).first()
            if not stock:
                logger.warning(f"Stock {symbol} not found in DB — skipping")
                continue
            try:
                candles = self.provider.get_daily_candles(
                    symbol=symbol, from_date=from_date, to_date=to_date
                )
                inserted = self._bulk_upsert_daily_candles(stock.id, candles)
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
        """Sync intraday candles for 5m, 15m, 1h resolutions."""
        if resolutions is None:
            resolutions = ["5m", "15m", "1h"]
        if symbols is None:
            symbols = [s.symbol for s in self.db.query(Stock).all()]

        to_date = datetime.utcnow()
        from_date = to_date - timedelta(days=days_back)

        for symbol in symbols:
            stock = self.db.query(Stock).filter_by(symbol=symbol).first()
            if not stock:
                continue
            for resolution in resolutions:
                try:
                    candles = self.provider.get_intraday_candles(
                        symbol=symbol,
                        resolution=resolution,
                        from_date=from_date,
                        to_date=to_date,
                    )
                    inserted = self._bulk_upsert_intraday_candles(stock.id, resolution, candles)
                    logger.info(f"sync_intraday {symbol} {resolution}: {inserted} new rows")
                except Exception as e:
                    logger.error(f"Failed to sync intraday {symbol} {resolution}: {e}")
                    self.db.rollback()
            time.sleep(self.rate_limit_delay)  # Once per symbol, not per resolution

    def sync_news(
        self,
        symbols: Optional[List[str]] = None,
        countback: int = 50,
    ) -> None:
        """Sync news articles for all stocks."""
        if symbols is None:
            symbols = [s.symbol for s in self.db.query(Stock).all()]

        for symbol in symbols:
            stock = self.db.query(Stock).filter_by(symbol=symbol).first()
            if not stock:
                continue
            try:
                articles = self.provider.get_news(symbol=symbol, countback=countback)
                for article in articles:
                    stmt = (
                        pg_insert(StockNews)
                        .values(
                            stock_id=stock.id,
                            headline=article.headline,
                            content=article.content,
                            source=article.source,
                            publication_date=article.publication_date,
                        )
                        .on_conflict_do_nothing()
                    )
                    self.db.execute(stmt)
                self.db.commit()
                time.sleep(self.rate_limit_delay)
            except Exception as e:
                logger.error(f"Failed to sync news {symbol}: {e}")
                self.db.rollback()

    def sync_earnings(self, symbols: Optional[List[str]] = None) -> None:
        """Sync earnings calendar."""
        if symbols is None:
            symbols = [s.symbol for s in self.db.query(Stock).all()]

        for symbol in symbols:
            stock = self.db.query(Stock).filter_by(symbol=symbol).first()
            if not stock:
                continue
            try:
                earnings = self.provider.get_earnings_history(symbol=symbol)
                rows = [
                    {
                        "stock_id": stock.id,
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
