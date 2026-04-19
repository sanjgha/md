"""Pydantic schemas for stocks API."""

from datetime import datetime
from typing import List

from pydantic import BaseModel, Field


class CandleResponse(BaseModel):
    """Single OHLCV candle response."""

    time: datetime = Field(
        ..., description="Candle timestamp (datetime for intraday, date for daily)"
    )
    open: float = Field(..., gt=0, description="Opening price")
    high: float = Field(..., gt=0, description="Highest price")
    low: float = Field(..., gt=0, description="Lowest price")
    close: float = Field(..., gt=0, description="Closing price")
    volume: int = Field(..., ge=0, description="Trading volume")

    class Config:
        """Pydantic config."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class CandlesResponse(BaseModel):
    """Response wrapper for candle array."""

    candles: List[CandleResponse] = Field(
        default_factory=list, description="Array of OHLCV candles"
    )
