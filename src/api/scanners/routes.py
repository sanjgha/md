"""Scanner API routes."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db
from src.api.scanners.schemas import ScannerMeta
from src.db.models import User

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
