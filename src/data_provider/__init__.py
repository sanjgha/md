"""Data provider package."""

from src.data_provider.base import Candle, DataProvider, Earning, NewsArticle, Quote
from src.data_provider.batch import get_realtime_quotes_batch
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
]
