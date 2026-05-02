"""Data provider package."""

from src.data_provider.base import Candle, DataProvider, Earning, NewsArticle, Quote
from src.data_provider.batch import get_realtime_quotes_batch
from src.data_provider.batch_candles import get_daily_candles_batch, get_intraday_candles_batch
from src.data_provider.bulk_candles_by_day import (
    get_bulk_candles_for_date,
    get_bulk_candles_for_date_range,
    get_bulk_candles_latest,
)
from src.data_provider.exceptions import (
    APIConnectionError,
    DataProviderError,
    RateLimitError,
    SymbolNotFoundError,
)

__all__ = [
    "DataProvider",
    "Candle",
    "Quote",
    "NewsArticle",
    "Earning",
    "DataProviderError",
    "RateLimitError",
    "SymbolNotFoundError",
    "APIConnectionError",
    "get_realtime_quotes_batch",
    "get_daily_candles_batch",
    "get_intraday_candles_batch",
    "get_bulk_candles_for_date",
    "get_bulk_candles_for_date_range",
    "get_bulk_candles_latest",
]
