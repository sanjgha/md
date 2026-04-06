"""Data provider exceptions."""


class DataProviderError(Exception):
    """Base exception for data provider errors."""

    pass


class RateLimitError(DataProviderError):
    """Raised when API rate limit is exceeded."""

    pass


class SymbolNotFoundError(DataProviderError):
    """Raised when symbol is not found."""

    pass


class APIConnectionError(DataProviderError):
    """Raised when API connection fails."""

    pass
