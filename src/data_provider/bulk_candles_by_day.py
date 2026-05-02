"""Bulk candle fetching using the /bulkcandles endpoint - fetch by date for all symbols."""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List

import requests

from src.data_provider.base import Candle

logger = logging.getLogger(__name__)


def get_bulk_candles_for_date(
    api_token: str,
    base_url: str,
    date: datetime,
    symbols: List[str],
) -> Dict[str, Candle]:
    """Fetch one daily candle for multiple symbols for a specific date.

    Uses the /stocks/bulkcandles/D/ endpoint which returns one candle per symbol.

    Args:
        api_token: MarketData.app API token
        base_url: Base URL for API
        date: The specific date to fetch candles for
        symbols: List of stock symbols (if None, uses snapshot mode for all available)

    Returns:
        Dict mapping symbol -> Candle (only successfully fetched symbols)
    """
    if symbols:
        symbol_param = ",".join(symbols)
        params = {"symbols": symbol_param}
    else:
        params = {}

    params["date"] = date.strftime("%Y-%m-%d")

    url = f"{base_url}/stocks/bulkcandles/D/"
    headers = {"Authorization": f"Bearer {api_token}"}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if data.get("s") != "ok" or not data.get("symbol"):
            return {}

        result: Dict[str, Candle] = {}
        for i, symbol in enumerate(data["symbol"]):
            result[symbol] = Candle(
                timestamp=date,
                open=float(data["o"][i]),
                high=float(data["h"][i]),
                low=float(data["l"][i]),
                close=float(data["c"][i]),
                volume=int(data["v"][i]),
            )

        return result

    except Exception as e:
        logger.error(f"Failed to fetch bulk candles for {date}: {e}")
        return {}


def get_bulk_candles_for_date_range(
    api_token: str,
    base_url: str,
    from_date: datetime,
    to_date: datetime,
    symbols: List[str],
) -> Dict[str, List[Candle]]:
    """Fetch daily candles for multiple symbols over a date range using bulk endpoint.

    Makes one API call per day, returning all symbols for each day.
    This is efficient when: num_days < num_symbols

    Args:
        api_token: MarketData.app API token
        base_url: Base URL for API
        from_date: Start date (inclusive)
        to_date: End date (inclusive)
        symbols: List of stock symbols

    Returns:
        Dict mapping symbol -> List[Candle] sorted by timestamp
    """
    result: Dict[str, List[Candle]] = {s: [] for s in symbols}

    current_date = from_date
    while current_date <= to_date:
        logger.debug(f"Fetching bulk candles for {current_date.date()}")
        candles_for_date = get_bulk_candles_for_date(api_token, base_url, current_date, symbols)

        for symbol, candle in candles_for_date.items():
            if symbol in result:
                result[symbol].append(candle)

        current_date += timedelta(days=1)

    # Sort each symbol's candles by timestamp
    for symbol in result:
        result[symbol].sort(key=lambda c: c.timestamp)

    return result


def get_bulk_candles_latest(
    api_token: str,
    base_url: str,
    symbols: List[str],
) -> Dict[str, Candle]:
    """Fetch the latest (most recent) daily candle for multiple symbols.

    This is the most efficient method for daily incremental sync - 1 API call
    regardless of number of symbols.

    Args:
        api_token: MarketData.app API token
        base_url: Base URL for API
        symbols: List of stock symbols

    Returns:
        Dict mapping symbol -> Candle
    """
    symbol_param = ",".join(symbols)
    url = f"{base_url}/stocks/bulkcandles/D/"
    headers = {"Authorization": f"Bearer {api_token}"}
    params = {"symbols": symbol_param}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        if data.get("s") != "ok" or not data.get("symbol"):
            return {}

        result: Dict[str, Candle] = {}
        for i, symbol in enumerate(data["symbol"]):
            # Parse timestamp from response
            ts = datetime.fromtimestamp(data["t"][i], tz=timezone.utc).replace(tzinfo=None)
            result[symbol] = Candle(
                timestamp=ts,
                open=float(data["o"][i]),
                high=float(data["h"][i]),
                low=float(data["l"][i]),
                close=float(data["c"][i]),
                volume=int(data["v"][i]),
            )

        return result

    except Exception as e:
        logger.error(f"Failed to fetch latest bulk candles: {e}")
        return {}
