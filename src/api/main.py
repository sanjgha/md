"""FastAPI application factory."""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.api.auth import SessionMiddleware
from src.api.deps import _session_factory
from src.api.routes.auth_routes import router as auth_router
from src.api.routes.health import router as health_router
from src.api.routes.me import router as me_router
from src.api.routes.settings import router as settings_router
from src.api.schedule.manager import schedule_manager
from src.api.schedule.routes import router as schedule_router
from src.api.scanners.routes import router as scanners_router
from src.api.stocks import router as stocks_router
from src.api.watchlists.routes import router as watchlists_router
from src.api.ws import heartbeat_loop, pubsub, ws_endpoint

FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the heartbeat background task and schedule manager, clean up on shutdown."""
    interval = float(os.environ.get("HEARTBEAT_INTERVAL", "5.0"))
    task = asyncio.create_task(heartbeat_loop(pubsub, interval))

    # Start the schedule manager
    db = _session_factory()()
    try:
        schedule_manager.start(db)
    except Exception:
        # Ensure we don't leave a half-initialized scheduler
        schedule_manager.stop()
        raise
    finally:
        db.close()

    try:
        yield
    finally:
        task.cancel()
        await pubsub.close_all()
        schedule_manager.stop()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(lifespan=lifespan, title="market-data")
    app.add_middleware(SessionMiddleware)
    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(me_router, prefix="/api")
    app.include_router(settings_router, prefix="/api/settings")
    app.include_router(scanners_router, prefix="/api/scanners")
    app.include_router(stocks_router, prefix="/api/stocks", tags=["stocks"])
    app.include_router(watchlists_router, prefix="/api/watchlists")
    app.include_router(schedule_router, prefix="/api/schedule/jobs", tags=["schedule"])
    app.add_api_websocket_route("/ws", ws_endpoint)
    if FRONTEND_DIST.exists():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
    return app
