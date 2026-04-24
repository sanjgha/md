"""Async batch quote fetching from MarketData.app."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List

import aiohttp

from src.data_provider.base import DataProvider, Quote
from src.data_provider.exceptions import APIConnectionError

logger = logging.getLogger(__name__)


async def get_realtime_quotes_batch(
    provider: DataProvider,
    symbols: List[str],
) -> List[Quote]:
    """Fetch multiple quotes efficiently using batch or parallel requests.

    Strategy:
    1. Try comma-separated symbols in single request
    2. If that fails, fall back to parallel async requests

    Args:
        provider: DataProvider instance with base_url
        symbols: List of stock symbols to fetch

    Returns:
        List of Quote objects (one per symbol)

    Raises:
        APIConnectionError: If all requests fail
    """
    if not symbols:
        return []

    # Try comma-separated batch request
    try:
        return await _fetch_batch_comma_separated(provider, symbols)
    except Exception as e:
        logger.debug(f"Batch request failed: {e}, falling back to parallel")

    # Fallback: parallel individual requests
    return await _fetch_parallel(provider, symbols)


async def _fetch_batch_comma_separated(
    provider: DataProvider,
    symbols: List[str],
) -> List[Quote]:
    """Try fetching all symbols in one comma-separated request.

    Args:
        provider: DataProvider instance
        symbols: List of symbols

    Returns:
        List of Quote objects

    Raises:
        APIConnectionError: If request fails
        ValueError: If provider doesn't have base_url attribute
    """
    symbol_str = ",".join(symbols)
    base_url = getattr(provider, "base_url", None)
    if not base_url:
        raise ValueError("Provider must have base_url attribute")

    url = f"{base_url}/stocks/quotes/{symbol_str}/"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=(5, 30)) as response:
            response.raise_for_status()
            data = await response.json()

    if data.get("s") != "ok":
        raise APIConnectionError(f"Batch quote response error: {data}")

    # Parse columnar response format
    quotes = []
    for i, symbol in enumerate(symbols):
        quotes.append(
            Quote(
                timestamp=datetime.fromtimestamp(data["updated"][i], tz=timezone.utc).replace(
                    tzinfo=None
                ),
                bid=float(data["bid"][i]),
                ask=float(data["ask"][i]),
                bid_size=int(data["bidSize"][i]),
                ask_size=int(data["askSize"][i]),
                last=float(data["last"][i]),
                volume=int(data["volume"][i]),
                change=float(data["change"][i]),
                change_pct=float(data["changepct"][i]),
            )
        )

    return quotes


async def _fetch_parallel(
    provider: DataProvider,
    symbols: List[str],
) -> List[Quote]:
    """Fetch quotes in parallel using async requests.

    Limits concurrent requests to 10 to avoid overwhelming the API.
    Skips symbols that return 404 (not found) errors.

    Args:
        provider: DataProvider instance
        symbols: List of symbols

    Returns:
        List of Quote objects (excluding symbols that failed)
    """
    semaphore = asyncio.Semaphore(10)

    async def fetch_one(symbol: str) -> Quote | None:
        async with semaphore:
            try:
                # Run sync method in thread pool to avoid blocking event loop
                return await asyncio.to_thread(provider.get_realtime_quote, symbol)
            except Exception as e:
                # Skip symbols that are not found or return errors
                if "404" in str(e) or "not found" in str(e).lower():
                    logger.warning(f"Skipping symbol {symbol}: {e}")
                    return None
                # Re-raise other errors
                raise

    tasks = [fetch_one(symbol) for symbol in symbols]
    results = await asyncio.gather(*tasks)
    # Filter out None values (failed symbols)
    return [r for r in results if r is not None]
