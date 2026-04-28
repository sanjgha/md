"""Service layer for stocks API."""

from datetime import date, datetime, timedelta
from typing import List, cast

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.api.stocks.schemas import CandleResponse
from src.db.models import DailyCandle, IntradayCandle, RealtimeQuote, Stock


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
        """Fetch daily candles.

        Uses exclusive upper bound (end_date + 1 day) to include all candles
        on the end_date, regardless of their time component.
        """
        # Use exclusive upper bound to include all candles on end_date
        exclusive_end = end_date + timedelta(days=1)

        stmt = (
            select(DailyCandle)
            .where(
                DailyCandle.stock_id == stock_id,
                DailyCandle.timestamp >= start_date,
                DailyCandle.timestamp < exclusive_end,
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

    def get_intraday_with_realtime(
        self,
        symbol: str,
        resolution: str = "1h",
    ) -> dict:
        """Get today's intraday candles and latest realtime quote.

        Args:
            symbol: Stock ticker
            resolution: Candle resolution (5m, 15m, 1h)

        Returns:
            Dict with 'intraday' (list of CandleResponse) and
            'realtime' (QuoteResponse or None)

        Raises:
            HTTPException: 404 if symbol not found
        """
        # Validate resolution
        if resolution not in {"5m", "15m", "1h"}:
            raise ValueError(f"Invalid resolution: {resolution}")

        # Resolve stock_id
        stock = self.db_session.execute(
            select(Stock).where(Stock.symbol == symbol.upper())
        ).scalar_one_or_none()

        if not stock:
            raise HTTPException(status_code=404, detail=f"Stock not found: {symbol}")

        # Get today's intraday candles
        today = date.today()
        intraday_stmt = (
            select(IntradayCandle)
            .where(
                IntradayCandle.stock_id == stock.id,
                IntradayCandle.resolution == resolution,
                func.date(IntradayCandle.timestamp) == today,
            )
            .order_by(IntradayCandle.timestamp.asc())
        )

        intraday_results = self.db_session.execute(intraday_stmt).scalars().all()

        candles = [
            {
                "time": int(c.timestamp.timestamp()),
                "open": float(c.open),
                "high": float(c.high),
                "low": float(c.low),
                "close": float(c.close),
                "volume": c.volume,
            }
            for c in intraday_results
        ]

        # Get latest realtime quote
        realtime_stmt = (
            select(RealtimeQuote)
            .where(
                RealtimeQuote.stock_id == stock.id,
                func.date(RealtimeQuote.timestamp) == today,
            )
            .order_by(RealtimeQuote.timestamp.desc())
            .limit(1)
        )

        realtime_row = self.db_session.execute(realtime_stmt).scalar_one_or_none()

        realtime = None
        if realtime_row:
            realtime = {
                "symbol": symbol,
                "last": float(realtime_row.last) if realtime_row.last else None,
                "change": float(realtime_row.change) if realtime_row.change else None,
                "change_pct": float(realtime_row.change_pct) if realtime_row.change_pct else None,
                "source": "realtime",
                "date": None,
            }

        return {"intraday": candles, "realtime": realtime}
