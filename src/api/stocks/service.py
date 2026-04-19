"""Service layer for stocks API."""

from datetime import datetime
from typing import List, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.stocks.schemas import CandleResponse
from src.db.models import DailyCandle, IntradayCandle, Stock


class StockService:
    """Service layer for stock candle data."""

    # Resolution to max range mapping (days)
    MAX_RANGES = {
        "5m": 7,
        "15m": 30,
        "1h": 90,
        "D": 730,  # 2 years
    }

    # Valid resolutions
    VALID_RESOLUTIONS = {"5m", "15m", "1h", "D"}

    def __init__(self, db_session: Session):
        """Initialize service with database session.

        Args:
            db_session: SQLAlchemy Session
        """
        self.db_session = db_session

    def get_candles(
        self,
        symbol: str,
        resolution: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[CandleResponse]:
        """Fetch OHLCV candles for a symbol.

        Args:
            symbol: Stock ticker symbol
            resolution: Timeframe (5m, 15m, 1h, D)
            start_date: Start of query range
            end_date: End of query range

        Returns:
            List of candle responses

        Raises:
            ValueError: If resolution is invalid or date range exceeds max
        """
        # Validate resolution
        if resolution not in self.VALID_RESOLUTIONS:
            raise ValueError(f"Invalid resolution: {resolution}")

        # Validate max range
        max_range_days = self.MAX_RANGES[resolution]
        actual_range = (end_date - start_date).days
        if actual_range > max_range_days:
            raise ValueError(
                f"Date range {actual_range} days exceeds max {max_range_days} for resolution {resolution}"
            )

        # Resolve stock_id
        stock = self.db_session.execute(
            select(Stock).where(Stock.symbol == symbol.upper())
        ).scalar_one_or_none()

        if not stock:
            raise ValueError(f"Stock not found: {symbol}")

        # Route to appropriate table
        if resolution in {"5m", "15m", "1h"}:
            return self._get_intraday_candles(int(stock.id), resolution, start_date, end_date)
        else:  # resolution == "D"
            return self._get_daily_candles(int(stock.id), start_date, end_date)

    def _get_intraday_candles(
        self,
        stock_id: int,
        resolution: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[CandleResponse]:
        """Fetch intraday candles."""
        stmt = (
            select(IntradayCandle)
            .where(
                IntradayCandle.stock_id == stock_id,
                IntradayCandle.resolution == resolution,
                IntradayCandle.timestamp >= start_date,
                IntradayCandle.timestamp <= end_date,
            )
            .order_by(IntradayCandle.timestamp.asc())
        )

        results = self.db_session.execute(stmt).scalars().all()

        return [
            CandleResponse(
                time=cast(datetime, c.timestamp),
                open=float(c.open),
                high=float(c.high),
                low=float(c.low),
                close=float(c.close),
                volume=int(c.volume),
            )
            for c in results
        ]

    def _get_daily_candles(
        self,
        stock_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> List[CandleResponse]:
        """Fetch daily candles."""
        stmt = (
            select(DailyCandle)
            .where(
                DailyCandle.stock_id == stock_id,
                DailyCandle.timestamp >= start_date,
                DailyCandle.timestamp <= end_date,
            )
            .order_by(DailyCandle.timestamp.asc())
        )

        results = self.db_session.execute(stmt).scalars().all()

        return [
            CandleResponse(
                time=cast(datetime, c.timestamp),
                open=float(c.open),
                high=float(c.high),
                low=float(c.low),
                close=float(c.close),
                volume=int(c.volume),
            )
            for c in results
        ]
