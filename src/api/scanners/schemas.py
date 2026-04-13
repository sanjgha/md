"""Pydantic schemas for scanner API."""
from pydantic import BaseModel


class ScannerMeta(BaseModel):
    """Scanner metadata returned by list endpoint."""

    name: str
    timeframe: str
    description: str


class ScannerResultItem(BaseModel):
    """Single scanner result for a ticker."""

    scanner_name: str
    symbol: str
    score: float | None
    signal: str | None
    price: float | None
    volume: int | None
    change_pct: float | None
    indicators_fired: list[str]
    matched_at: str  # ISO datetime


class ScannerResultsResponse(BaseModel):
    """Response from GET /api/scanners/results."""

    results: list[ScannerResultItem]
    run_type: str
    date: str


class IntradayRunRequest(BaseModel):
    """Request body for POST /api/scanners/run."""

    scanners: list[str]
    timeframe: str  # '15m' | '1h'
    input_scope: str | int  # 'universe' or watchlist_id


class RunDateEntry(BaseModel):
    date: str
    run_type: str
    time: str
