"""MarketData.app DataProvider implementation with retry, validation, and timeouts."""

import logging
import time
from datetime import datetime
from typing import List, Optional

import requests

from src.data_provider.base import Candle, DataProvider, Earning, NewsArticle, Quote
from src.data_provider.exceptions import APIConnectionError, RateLimitError, SymbolNotFoundError
from src.data_provider.validation import validate_resolution, validate_symbol

logger = logging.getLogger(__name__)


class MarketDataAppProvider(DataProvider):
    """MarketData.app implementation with retry logic, validation, and timeouts."""

    def __init__(
        self,
        api_token: str,
        max_retries: int = 5,
        retry_backoff_base: int = 1,
    ):
        """Initialize provider with API token and retry configuration."""
        self.base_url = "https://api.marketdata.app/v1"
        self.api_token = api_token
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {api_token}"})
        self.max_retries = max_retries
        self.retry_backoff_base = retry_backoff_base

    def _request_with_retry(self, url: str, **kwargs) -> dict:
        """Make GET request with exponential backoff. Always uses timeout=(5, 30)."""
        last_error = None
        kwargs.setdefault("timeout", (5, 30))

        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(url, **kwargs)
                resp.raise_for_status()
                return resp.json()

            except requests.exceptions.HTTPError as e:
                if resp.status_code == 429:
                    raise RateLimitError(f"API rate limit exceeded: {e}")
                elif resp.status_code == 404:
                    raise SymbolNotFoundError(f"Symbol not found: {e}")
                last_error = e

            except requests.exceptions.RequestException as e:
                last_error = e

            if attempt < self.max_retries - 1:
                wait_time = self.retry_backoff_base**attempt
                time.sleep(wait_time)

        raise APIConnectionError(f"Failed after {self.max_retries} retries: {last_error}")

    def get_daily_candles(
        self,
        symbol: str,
        from_date: datetime,
        to_date: datetime,
    ) -> List[Candle]:
        """Fetch daily OHLCV candles using cached feed."""
        validate_symbol(symbol)
        url = f"{self.base_url}/stocks/candles/1d/{symbol}"
        params = {"from": from_date.isoformat(), "to": to_date.isoformat(), "feed": "cached"}
        data = self._request_with_retry(url, params=params)
        return [
            Candle(
                timestamp=datetime.fromisoformat(r["t"]),
                open=float(r["o"]),
                high=float(r["h"]),
                low=float(r["l"]),
                close=float(r["c"]),
                volume=int(r["v"]),
            )
            for r in data.get("results", [])
        ]

    def get_intraday_candles(
        self,
        symbol: str,
        resolution: str,
        from_date: datetime,
        to_date: datetime,
    ) -> List[Candle]:
        """Fetch intraday bars at specified resolution (5m, 15m, 1h)."""
        validate_symbol(symbol)
        validate_resolution(resolution)
        url = f"{self.base_url}/stocks/candles/{resolution}/{symbol}"
        params = {"from": from_date.isoformat(), "to": to_date.isoformat(), "feed": "cached"}
        data = self._request_with_retry(url, params=params)
        return [
            Candle(
                timestamp=datetime.fromisoformat(r["t"]),
                open=float(r["o"]),
                high=float(r["h"]),
                low=float(r["l"]),
                close=float(r["c"]),
                volume=int(r["v"]),
            )
            for r in data.get("results", [])
        ]

    def get_realtime_quote(self, symbol: str) -> Quote:
        """Fetch current Level-1 quote with intraday summary."""
        validate_symbol(symbol)
        url = f"{self.base_url}/stocks/quotes/{symbol}"
        data = self._request_with_retry(url, params={"feed": "live"})
        result = data["results"][0]
        return Quote(
            timestamp=datetime.fromisoformat(result["updated"]),
            bid=float(result["bid"]),
            ask=float(result["ask"]),
            bid_size=int(result["bidSize"]),
            ask_size=int(result["askSize"]),
            last=float(result["last"]),
            open=float(result["o"]),
            high=float(result["h"]),
            low=float(result["l"]),
            close=float(result["c"]),
            volume=int(result["volume"]),
            change=float(result["change"]),
            change_pct=float(result["changepct"]),
            week_52_high=float(result["52weekHigh"]),
            week_52_low=float(result["52weekLow"]),
            status=result["status"],
        )

    def get_earnings_history(
        self,
        symbol: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> List[Earning]:
        """Fetch historical earnings reports."""
        validate_symbol(symbol)
        url = f"{self.base_url}/stocks/earnings/{symbol}"
        params: dict = {}
        if from_date:
            params["from"] = from_date.isoformat()
        if to_date:
            params["to"] = to_date.isoformat()
        data = self._request_with_retry(url, params=params)
        return [
            Earning(
                symbol=symbol,
                fiscal_year=int(r["fiscalYear"]),
                fiscal_quarter=int(r["fiscalQuarter"]),
                earnings_date=datetime.fromisoformat(r["date"]),
                report_date=datetime.fromisoformat(r["reportDate"]),
                report_time=r["reportTime"],
                currency=r["currency"],
                reported_eps=float(r["reportedEPS"]),
                estimated_eps=float(r["estimatedEPS"]),
            )
            for r in data.get("results", [])
        ]

    def get_news(
        self,
        symbol: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        countback: Optional[int] = None,
    ) -> List[NewsArticle]:
        """Fetch news articles for a symbol."""
        validate_symbol(symbol)
        url = f"{self.base_url}/stocks/news/{symbol}"
        params: dict = {}
        if from_date:
            params["from"] = from_date.isoformat()
        if to_date:
            params["to"] = to_date.isoformat()
        if countback:
            params["countback"] = countback
        data = self._request_with_retry(url, params=params)
        headlines = data.get("headline", [])
        contents = data.get("content", [])
        sources = data.get("source", [])
        pub_dates = data.get("publicationDate", [])
        return [
            NewsArticle(
                symbol=symbol,
                headline=headline,
                content=contents[i] if i < len(contents) else "",
                source=sources[i] if i < len(sources) else "",
                publication_date=datetime.fromisoformat(pub_dates[i]),
            )
            for i, headline in enumerate(headlines)
        ]
