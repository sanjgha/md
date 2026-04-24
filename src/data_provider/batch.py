"""Async batch quote fetching from MarketData.app."""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, List

import aiohttp

from src.data_provider.base import DataProvider, Quote
from src.data_provider.exceptions import APIConnectionError

logger = logging.getLogger(__name__)


async def get_realtime_quotes_batch(
    provider: DataProvider,
    symbols: List[str],
) -> Dict[str, Quote]:
    """Fetch multiple quotes efficiently using batch or parallel requests.

    Strategy:
    1. Try comma-separated symbols in single request
    2. If that fails, fall back to parallel async requests

    Args:
        provider: DataProvider instance with base_url
        symbols: List of stock symbols to fetch

    Returns:
        Dict mapping symbol -> Quote (only successfully fetched symbols)

    Raises:
        APIConnectionError: If all requests fail
    """
    if not symbols:
        return {}

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
) -> Dict[str, Quote]:
    """Try fetching all symbols in one comma-separated request.

    Uses the `symbol` field in the API response to correctly map each quote
    to its symbol, regardless of response ordering or deduplication.

    Args:
        provider: DataProvider instance
        symbols: List of symbols

    Returns:
        Dict mapping symbol -> Quote

    Raises:
        APIConnectionError: If request fails
        ValueError: If provider doesn't have base_url attribute
    """
    # Deduplicate while preserving order for the request
    seen: set[str] = set()
    unique_symbols = [s for s in symbols if not (s in seen or seen.add(s))]  # type: ignore[func-returns-value]

    symbol_str = ",".join(unique_symbols)
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

    response_symbols = data.get("symbol", [])
    if not response_symbols:
        raise APIConnectionError("Batch response missing symbol array")

    # Build quotes keyed by symbol from response — safe regardless of API ordering
    result: Dict[str, Quote] = {}
    for i, sym in enumerate(response_symbols):
        result[sym] = Quote(
            timestamp=datetime.fromtimestamp(data["updated"][i], tz=timezone.utc).replace(
                tzinfo=None
            ),
            bid=float(data["bid"][i]),
            ask=float(data["ask"][i]),
            bid_size=int(data["bidSize"][i]),
            ask_size=int(data["askSize"][i]),
            last=float(data["last"][i]),
            open=float(data["open"][i]) if data.get("open") else 0.0,
            high=float(data["high"][i]) if data.get("high") else 0.0,
            low=float(data["low"][i]) if data.get("low") else 0.0,
            volume=int(data["volume"][i]),
            change=float(data["change"][i]),
            change_pct=float(data["changepct"][i]),
        )

    return result


async def _fetch_parallel(
    provider: DataProvider,
    symbols: List[str],
) -> Dict[str, Quote]:
    """Fetch quotes in parallel using async requests.

    Limits concurrent requests to 10 to avoid overwhelming the API.
    Skips symbols that return 404 (not found) errors.

    Args:
        provider: DataProvider instance
        symbols: List of symbols

    Returns:
        Dict mapping symbol -> Quote (excluding symbols that failed)
    """
    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_symbols = [s for s in symbols if not (s in seen or seen.add(s))]  # type: ignore[func-returns-value]

    semaphore = asyncio.Semaphore(10)

    async def fetch_one(symbol: str) -> tuple[str, Quote] | None:
        async with semaphore:
            try:
                # Run sync method in thread pool to avoid blocking event loop
                quote = await asyncio.to_thread(provider.get_realtime_quote, symbol)
                return (symbol, quote)
            except Exception as e:
                # Skip symbols that are not found or return errors
                if "404" in str(e) or "not found" in str(e).lower():
                    logger.warning(f"Skipping symbol {symbol}: {e}")
                    return None
                # Re-raise other errors
                raise

    tasks = [fetch_one(symbol) for symbol in unique_symbols]
    results = await asyncio.gather(*tasks)
    return {sym: q for entry in results if entry is not None for sym, q in [entry]}
