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
