"""Abstract DataProvider interface and data dataclasses."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class Candle:
    """OHLCV candle bar."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class Quote:
    """Realtime Level-1 quote with intraday summary."""

    timestamp: datetime
    bid: float
    ask: float
    bid_size: int
    ask_size: int
    last: float
    volume: int
    change: float
    change_pct: float
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    week_52_high: float = 0.0
    week_52_low: float = 0.0
    status: str = ""


@dataclass
class NewsArticle:
    """News article."""

    symbol: str
    headline: str
    content: str
    source: str
    publication_date: datetime


@dataclass
class Earning:
    """Earnings record."""

    symbol: str
    fiscal_year: int
    fiscal_quarter: int
    earnings_date: datetime
    report_date: datetime
    report_time: str
    currency: str
    reported_eps: float
    estimated_eps: float


class DataProvider(ABC):
    """Abstract interface for market data providers."""

    @abstractmethod
    def get_daily_candles(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime,
    ) -> List[Candle]:
        """Fetch daily OHLCV candles."""

    @abstractmethod
    def get_intraday_candles(
        self,
        symbol: str,
        resolution: str,
        from_date: datetime,
        to_date: datetime,
    ) -> List[Candle]:
        """Fetch intraday bars (5m, 15m, 1h)."""

    @abstractmethod
    def get_realtime_quote(self, symbol: str) -> Quote:
        """Fetch current bid/ask/last with intraday summary."""

    @abstractmethod
    def get_earnings_history(
        self,
        symbol: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> List[Earning]:
        """Fetch historical earnings."""

    @abstractmethod
    def get_news(
        self,
        symbol: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        countback: Optional[int] = None,
    ) -> List[NewsArticle]:
        """Fetch news articles."""
