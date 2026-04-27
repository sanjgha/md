"""MarketData.app DataProvider implementation with retry, validation, and timeouts."""

import logging
import time
from datetime import datetime, timezone
from typing import List, Optional

import requests  # type: ignore[import-untyped]

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

    def _parse_candles(self, data: dict) -> List[Candle]:
        """Parse columnar candle response: {s, t, o, h, l, c, v} into Candle list."""
        if data.get("s") != "ok" or not data.get("t"):
            return []
        return [
            Candle(
                timestamp=datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None),
                open=float(o),
                high=float(h),
                low=float(low),
                close=float(c),
                volume=int(v),
            )
            for ts, o, h, low, c, v in zip(
                data["t"], data["o"], data["h"], data["l"], data["c"], data["v"]
            )
        ]

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
        params = {"from": from_date.strftime("%Y-%m-%d"), "to": to_date.strftime("%Y-%m-%d")}
        data = self._request_with_retry(url, params=params)
        return self._parse_candles(data)

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
        params = {"from": from_date.strftime("%Y-%m-%d"), "to": to_date.strftime("%Y-%m-%d")}
        data = self._request_with_retry(url, params=params)
        return self._parse_candles(data)

    def get_realtime_quote(self, symbol: str) -> Quote:
        """Fetch current Level-1 quote with intraday summary."""
        validate_symbol(symbol)
        url = f"{self.base_url}/stocks/quotes/{symbol}"
        data = self._request_with_retry(url)
        if data.get("s") != "ok" or not data.get("updated"):
            raise APIConnectionError(f"Unexpected quote response for {symbol}")
        return Quote(
            timestamp=datetime.fromtimestamp(data["updated"][0], tz=timezone.utc).replace(
                tzinfo=None
            ),
            bid=float(data["bid"][0]),
            ask=float(data["ask"][0]),
            bid_size=int(data["bidSize"][0]),
            ask_size=int(data["askSize"][0]),
            last=float(data["last"][0]),
            open=float(data["open"][0]) if data.get("open") else 0.0,
            high=float(data["high"][0]) if data.get("high") else 0.0,
            low=float(data["low"][0]) if data.get("low") else 0.0,
            volume=int(data["volume"][0]),
            change=float(data["change"][0]),
            change_pct=float(data["changepct"][0]),
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
            params["from"] = from_date.strftime("%Y-%m-%d")
        if to_date:
            params["to"] = to_date.strftime("%Y-%m-%d")
        data = self._request_with_retry(url, params=params)
        if data.get("s") != "ok" or not data.get("fiscalYear"):
            return []
        return [
            Earning(
                symbol=symbol,
                fiscal_year=int(fy),
                fiscal_quarter=int(fq),
                earnings_date=datetime.fromtimestamp(d, tz=timezone.utc).replace(tzinfo=None),
                report_date=datetime.fromtimestamp(rd, tz=timezone.utc).replace(tzinfo=None),
                report_time=rt,
                currency=cur,
                reported_eps=float(eps) if eps is not None else 0.0,
                estimated_eps=float(est) if est is not None else 0.0,
            )
            for fy, fq, d, rd, rt, cur, eps, est in zip(
                data["fiscalYear"],
                data["fiscalQuarter"],
                data["date"],
                data["reportDate"],
                data["reportTime"],
                data["currency"],
                data["reportedEPS"],
                data["estimatedEPS"],
            )
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
            params["from"] = from_date.strftime("%Y-%m-%d")
        if to_date:
            params["to"] = to_date.strftime("%Y-%m-%d")
        if countback:
            params["countback"] = countback
        data = self._request_with_retry(url, params=params)
        if data.get("s") != "ok" or not data.get("headline"):
            return []
        return [
            NewsArticle(
                symbol=symbol,
                headline=headline,
                content=content,
                source=source,
                publication_date=datetime.fromtimestamp(pub_date, tz=timezone.utc).replace(
                    tzinfo=None
                ),
            )
            for headline, content, source, pub_date in zip(
                data["headline"],
                data.get("content", [""] * len(data["headline"])),
                data.get("source", [""] * len(data["headline"])),
                data["publicationDate"],
            )
        ]
