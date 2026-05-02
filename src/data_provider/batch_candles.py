"""Async batch candle fetching from MarketData.app."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import aiohttp
from aiohttp import ClientTimeout

from src.data_provider.base import Candle, DataProvider

logger = logging.getLogger(__name__)


async def get_daily_candles_batch(
    provider: DataProvider,
    symbols: List[str],
    from_date: datetime,
    to_date: datetime,
    max_concurrent: int = 10,
) -> Dict[str, List[Candle]]:
    """Fetch daily candles for multiple symbols efficiently using parallel async requests.

    Args:
        provider: DataProvider instance with base_url and api_token attributes
        symbols: List of stock symbols to fetch
        from_date: Start date for candle data
        to_date: End date for candle data
        max_concurrent: Maximum number of concurrent requests

    Returns:
        Dict mapping symbol -> List[Candle] (only successfully fetched symbols)

    Raises:
        ValueError: If provider lacks required attributes
    """
    if not symbols:
        return {}

    base_url = getattr(provider, "base_url", None)
    api_token = getattr(provider, "api_token", None)

    if not base_url or not api_token:
        raise ValueError(
            "Provider must have base_url and api_token attributes for batch fetching. "
            "Use use_batch=False with DataFetcher for providers without these attributes."
        )

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_symbols = [s for s in symbols if not (s in seen or seen.add(s))]  # type: ignore[func-returns-value]

    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_one(symbol: str) -> Optional[Tuple[str, List[Candle]]]:
        async with semaphore:
            url = f"{base_url}/stocks/candles/1d/{symbol}"
            params = {
                "from": from_date.strftime("%Y-%m-%d"),
                "to": to_date.strftime("%Y-%m-%d"),
                "adjusted": "true",
            }
            headers = {"Authorization": f"Bearer {api_token}"}

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url,
                        headers=headers,
                        params=params,
                        timeout=ClientTimeout(total=30, connect=5),
                    ) as response:
                        response.raise_for_status()
                        data = await response.json()

                        if data.get("s") != "ok" or not data.get("t"):
                            return (symbol, [])

                        candles = [
                            Candle(
                                timestamp=datetime.fromtimestamp(ts, tz=timezone.utc).replace(
                                    tzinfo=None
                                ),
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
                        return (symbol, candles)

            except Exception as e:
                logger.warning(f"Failed to fetch candles for {symbol}: {e}")
                return None

    tasks = [fetch_one(symbol) for symbol in unique_symbols]
    results = await asyncio.gather(*tasks)

    return {sym: candles for entry in results if entry is not None for sym, candles in [entry]}


async def get_intraday_candles_batch(
    provider: DataProvider,
    symbols: List[str],
    resolution: str,
    from_date: datetime,
    to_date: datetime,
    max_concurrent: int = 10,
) -> Dict[str, List[Candle]]:
    """Fetch intraday candles for multiple symbols efficiently using parallel async requests.

    Args:
        provider: DataProvider instance with base_url and api_token attributes
        symbols: List of stock symbols to fetch
        resolution: Candle resolution (5m, 15m, 1h, etc.)
        from_date: Start date for candle data
        to_date: End date for candle data
        max_concurrent: Maximum number of concurrent requests

    Returns:
        Dict mapping symbol -> List[Candle] (only successfully fetched symbols)

    Raises:
        ValueError: If provider lacks required attributes
    """
    if not symbols:
        return {}

    base_url = getattr(provider, "base_url", None)
    api_token = getattr(provider, "api_token", None)

    if not base_url or not api_token:
        raise ValueError(
            "Provider must have base_url and api_token attributes for batch fetching. "
            "Use use_batch=False with DataFetcher for providers without these attributes."
        )

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_symbols = [s for s in symbols if not (s in seen or seen.add(s))]  # type: ignore[func-returns-value]

    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_one(symbol: str) -> Optional[Tuple[str, List[Candle]]]:
        async with semaphore:
            url = f"{base_url}/stocks/candles/{resolution}/{symbol}"
            params = {
                "from": from_date.strftime("%Y-%m-%d"),
                "to": to_date.strftime("%Y-%m-%d"),
                "adjusted": "true",
            }
            headers = {"Authorization": f"Bearer {api_token}"}

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        url,
                        headers=headers,
                        params=params,
                        timeout=ClientTimeout(total=30, connect=5),
                    ) as response:
                        response.raise_for_status()
                        data = await response.json()

                        if data.get("s") != "ok" or not data.get("t"):
                            return (symbol, [])

                        candles = [
                            Candle(
                                timestamp=datetime.fromtimestamp(ts, tz=timezone.utc).replace(
                                    tzinfo=None
                                ),
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
                        return (symbol, candles)

            except Exception as e:
                logger.warning(f"Failed to fetch intraday candles for {symbol}: {e}")
                return None

    tasks = [fetch_one(symbol) for symbol in unique_symbols]
    results = await asyncio.gather(*tasks)

    return {sym: candles for entry in results if entry is not None for sym, candles in [entry]}
