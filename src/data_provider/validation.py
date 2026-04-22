"""Input validation for market data provider requests."""

import re

from src.data_provider.exceptions import DataProviderError, SymbolNotFoundError

VALID_RESOLUTIONS = frozenset({"5m", "15m", "1h"})
_SYMBOL_RE = re.compile(r"^[A-Z]{1,10}$")


def validate_symbol(symbol: str) -> str:
    """Validate ticker symbol format; raise SymbolNotFoundError if invalid."""
    if not _SYMBOL_RE.match(symbol):
        raise SymbolNotFoundError(f"Invalid symbol format: {symbol!r}")
    return symbol


def validate_resolution(resolution: str) -> str:
    """Validate candle resolution; raise DataProviderError if not in allowed set."""
    if resolution not in VALID_RESOLUTIONS:
        raise DataProviderError(
            f"Invalid resolution {resolution!r}. Must be one of: {sorted(VALID_RESOLUTIONS)}"
        )
    return resolution
