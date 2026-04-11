"""FastAPI application factory."""

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.api.auth import SessionMiddleware
from src.api.routes.auth_routes import router as auth_router
from src.api.routes.health import router as health_router
from src.api.routes.me import router as me_router
from src.api.routes.settings import router as settings_router
from src.api.ws import heartbeat_loop, pubsub, ws_endpoint

FRONTEND_DIST = Path(__file__).parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the heartbeat background task and clean up on shutdown."""
    interval = float(os.environ.get("HEARTBEAT_INTERVAL", "5.0"))
    task = asyncio.create_task(heartbeat_loop(pubsub, interval))
    try:
        yield
    finally:
        task.cancel()
        await pubsub.close_all()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    app = FastAPI(lifespan=lifespan, title="market-data")
    app.add_middleware(SessionMiddleware)
    app.include_router(health_router, prefix="/api")
    app.include_router(auth_router, prefix="/api/auth")
    app.include_router(me_router, prefix="/api")
    app.include_router(settings_router, prefix="/api/settings")
    app.add_api_websocket_route("/ws", ws_endpoint)
    if FRONTEND_DIST.exists():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
    return app
