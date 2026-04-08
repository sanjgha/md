"""GET /api/health — liveness probe."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health():
    """Return service liveness status."""
    return {"status": "ok"}
