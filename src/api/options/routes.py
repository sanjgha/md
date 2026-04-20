"""Options API routes."""

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.options.schemas import IVRResponse, RegimeResponse
from src.db.models import IVRSnapshot, RegimeSnapshot

router = APIRouter()


def _to_date(value: Any) -> date:
    """Coerce a datetime or date value to date."""
    if isinstance(value, datetime):
        return value.date()
    return value  # type: ignore[return-value]


def _snap_to_response(snap: IVRSnapshot) -> IVRResponse:
    return IVRResponse(
        symbol=str(snap.symbol),
        ivr=float(snap.ivr),  # type: ignore[arg-type]
        current_hv=float(snap.current_hv),  # type: ignore[arg-type]
        calculation_basis=str(snap.calculation_basis),
        as_of_date=_to_date(snap.as_of_date),
    )


@router.get("/ivr/{symbol}", response_model=IVRResponse)
def get_ivr(symbol: str, db: Session = Depends(get_db)) -> IVRResponse:
    """Get the latest IVR snapshot for a symbol."""
    snap = (
        db.query(IVRSnapshot)
        .filter_by(symbol=symbol.upper())
        .order_by(IVRSnapshot.as_of_date.desc())
        .first()
    )
    if not snap:
        raise HTTPException(status_code=404, detail=f"No IVR data for {symbol}")
    return _snap_to_response(snap)


@router.get("/ivr", response_model=list[IVRResponse])
def get_ivr_bulk(symbols: str = Query(...), db: Session = Depends(get_db)) -> list[IVRResponse]:
    """Get the latest IVR snapshots for multiple comma-separated symbols."""
    syms = [s.strip().upper() for s in symbols.split(",")]
    latest_dates = (
        db.query(
            IVRSnapshot.symbol,
            func.max(IVRSnapshot.as_of_date).label("max_date"),
        )
        .filter(IVRSnapshot.symbol.in_(syms))
        .group_by(IVRSnapshot.symbol)
        .subquery()
    )
    snaps = (
        db.query(IVRSnapshot)
        .join(
            latest_dates,
            (IVRSnapshot.symbol == latest_dates.c.symbol)
            & (IVRSnapshot.as_of_date == latest_dates.c.max_date),
        )
        .all()
    )
    return [_snap_to_response(s) for s in snaps]


@router.get("/regime/{symbol}", response_model=RegimeResponse)
def get_regime(symbol: str, db: Session = Depends(get_db)) -> RegimeResponse:
    """Get the latest regime snapshot for a symbol."""
    snap = (
        db.query(RegimeSnapshot)
        .filter_by(symbol=symbol.upper())
        .order_by(RegimeSnapshot.as_of_date.desc())
        .first()
    )
    if not snap:
        raise HTTPException(status_code=404, detail=f"No regime data for {symbol}")
    return RegimeResponse(
        symbol=symbol.upper(),
        regime=str(snap.regime),
        direction=str(snap.direction) if snap.direction else None,
        adx=float(snap.adx or 0),  # type: ignore[arg-type]
        atr_pct=float(snap.atr_pct or 0),  # type: ignore[arg-type]
        as_of_date=_to_date(snap.as_of_date),
    )
