"""Scanner API routes."""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db
from src.api.scanners.schemas import RunDateEntry, ScannerMeta, ScannerResultItem, ScannerResultsResponse
from src.db.models import RealtimeQuote, ScannerResult, Stock, User

router = APIRouter()


def _get_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Resolve authenticated user from request.state.user_id."""
    return get_current_user(request, db)


def _build_registry():
    """Build scanner registry from registered scanners."""
    from src.scanner.registry import ScannerRegistry
    from src.scanner.scanners.momentum_scan import MomentumScanner
    from src.scanner.scanners.price_action import PriceActionScanner
    from src.scanner.scanners.volume_scan import VolumeScanner

    registry = ScannerRegistry()
    registry.register("momentum", MomentumScanner())
    registry.register("price_action", PriceActionScanner())
    registry.register("volume", VolumeScanner())
    return registry


@router.get("", response_model=list[ScannerMeta])
def list_scanners(user: User = Depends(_get_user)):
    """List all registered scanners with name, timeframe, and description."""
    registry = _build_registry()
    return [
        ScannerMeta(name=name, timeframe=scanner.timeframe, description=scanner.description)
        for name, scanner in registry.list().items()
    ]


@router.get("/results", response_model=ScannerResultsResponse)
def get_results(
    scanners: Optional[str] = Query(None, description="Comma-separated scanner names"),
    run_type: str = Query("eod", description="'eod' or 'pre_close'"),
    date: Optional[str] = Query(None, description="ISO date (YYYY-MM-DD) or omit for latest"),
    user: User = Depends(_get_user),
    db: Session = Depends(get_db),
):
    """Query scanner_results with optional filters. Defaults to latest date."""
    from datetime import datetime

    # Resolve date: latest matched_at date if not specified
    if date is None:
        latest = (
            db.query(ScannerResult.matched_at)
            .order_by(ScannerResult.matched_at.desc())
            .first()
        )
        if latest is None:
            return ScannerResultsResponse(results=[], run_type=run_type, date="")
        resolved_date = latest[0].date()
    else:
        resolved_date = datetime.strptime(date, "%Y-%m-%d").date()

    scanner_names = [s.strip() for s in scanners.split(",")] if scanners else None

    # Filter to the resolved date (match on date portion of matched_at)
    start = datetime.combine(resolved_date, datetime.min.time())
    end = datetime.combine(resolved_date, datetime.max.time())

    query = (
        db.query(ScannerResult, Stock)
        .join(Stock, ScannerResult.stock_id == Stock.id)
        .filter(
            ScannerResult.run_type == run_type,
            ScannerResult.matched_at.between(start, end),
        )
    )

    if scanner_names:
        query = query.filter(ScannerResult.scanner_name.in_(scanner_names))

    rows = query.all()

    results = []
    for sr, stock in rows:
        meta = sr.result_metadata or {}
        # Attempt to get latest quote for price/volume data
        quote = (
            db.query(RealtimeQuote)
            .filter(RealtimeQuote.stock_id == stock.id)
            .order_by(RealtimeQuote.timestamp.desc())
            .first()
        )
        results.append(
            ScannerResultItem(
                scanner_name=sr.scanner_name,
                symbol=stock.symbol,
                score=meta.get("score"),
                signal=meta.get("reason") or meta.get("signal"),
                price=float(quote.last) if quote and quote.last else None,
                volume=int(quote.volume) if quote and quote.volume else None,
                change_pct=float(quote.change_pct) if quote and quote.change_pct else None,
                indicators_fired=[k for k, v in meta.items() if isinstance(v, bool) and v],
                matched_at=sr.matched_at.isoformat(),
            )
        )

    return ScannerResultsResponse(
        results=results,
        run_type=run_type,
        date=resolved_date.isoformat(),
    )


@router.get("/run-dates", response_model=list[RunDateEntry])
def get_run_dates(
    user: User = Depends(_get_user),
    db: Session = Depends(get_db),
):
    """Return distinct (date, run_type, time) entries for the past 5 trading days."""
    from sqlalchemy import func

    rows = (
        db.query(
            func.date(ScannerResult.matched_at).label("date"),
            ScannerResult.run_type,
            func.max(ScannerResult.matched_at).label("latest_ts"),
        )
        .group_by(func.date(ScannerResult.matched_at), ScannerResult.run_type)
        .order_by(func.date(ScannerResult.matched_at).desc(), ScannerResult.run_type)
        .limit(20)
        .all()
    )
    return [
        RunDateEntry(
            date=str(row.date),
            run_type=row.run_type,
            time=row.latest_ts.strftime("%H:%M"),
        )
        for row in rows
    ]
