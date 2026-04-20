"""Pydantic schemas for options API responses."""

from pydantic import BaseModel
from datetime import date


class IVRResponse(BaseModel):
    """IV Rank response for a single symbol."""

    symbol: str
    ivr: float
    current_hv: float
    calculation_basis: str
    as_of_date: date


class RegimeResponse(BaseModel):
    """Market regime response for a single symbol."""

    symbol: str
    regime: str
    direction: str | None
    adx: float
    atr_pct: float
    as_of_date: date
