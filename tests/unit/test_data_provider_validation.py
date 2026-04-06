"""Tests for input validation functions."""

import pytest
from src.data_provider.validation import validate_symbol, validate_resolution
from src.data_provider.exceptions import SymbolNotFoundError, DataProviderError


def test_validate_symbol_valid():
    """Valid symbols pass validation."""
    assert validate_symbol("AAPL") == "AAPL"
    assert validate_symbol("BRK") == "BRK"


def test_validate_symbol_invalid():
    """Invalid symbols raise SymbolNotFoundError."""
    with pytest.raises(SymbolNotFoundError):
        validate_symbol("aapl")  # lowercase
    with pytest.raises(SymbolNotFoundError):
        validate_symbol("TOOLONGSYMBOL")  # > 10 chars
    with pytest.raises(SymbolNotFoundError):
        validate_symbol("12AB")  # starts with digit
    with pytest.raises(SymbolNotFoundError):
        validate_symbol("")  # empty


def test_validate_resolution_valid():
    """Valid resolutions pass validation."""
    assert validate_resolution("5m") == "5m"
    assert validate_resolution("15m") == "15m"
    assert validate_resolution("1h") == "1h"


def test_validate_resolution_invalid():
    """Invalid resolutions raise DataProviderError."""
    with pytest.raises(DataProviderError):
        validate_resolution("1d")
    with pytest.raises(DataProviderError):
        validate_resolution("30m")
    with pytest.raises(DataProviderError):
        validate_resolution("")
