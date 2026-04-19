"""API routes for stocks candle data."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.stocks.schemas import CandleResponse
from src.api.stocks.service import StockService

router = APIRouter()


@router.get("/{symbol}/candles", response_model=list[CandleResponse])
def get_candles(
    symbol: str,
    resolution: str = Query(...),
    from_date: str = Query(..., alias="from", description="Start date (YYYY-MM-DD)"),
    to_date: str = Query(..., alias="to", description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
) -> list[CandleResponse]:
    """Get OHLCV candles for a symbol.

    Args:
        symbol: Stock ticker symbol
        resolution: Timeframe (5m, 15m, 1h, D)
        from_date: Start of date range
        to_date: End of date range
        db: Database session

    Returns:
        Array of OHLCV candles

    Raises:
        HTTPException: 404 if symbol not found, 400 for invalid params
    """
    service = StockService(db)

    try:
        start = datetime.fromisoformat(from_date)
        end = datetime.fromisoformat(to_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    try:
        candles = service.get_candles(
            symbol=symbol,
            resolution=resolution,
            start_date=start,
            end_date=end,
        )
        return candles
    except ValueError as e:
        # Check if it's a "stock not found" error
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        # Other validation errors
        raise HTTPException(status_code=400, detail=str(e))
