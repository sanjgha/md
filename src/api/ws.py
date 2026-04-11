"""WebSocket infrastructure: PubSubRegistry, ws_endpoint, heartbeat_loop."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class PubSubRegistry:
    """Thread-safe (asyncio) pub/sub registry mapping topic → set[WebSocket]."""

    def __init__(self):
        """Initialise empty subscription map and asyncio lock."""
        self._lock = asyncio.Lock()
        self._subs: dict[str, set[WebSocket]] = {}

    async def subscribe(self, ws: WebSocket, topic: str) -> None:
        """Add ws to the subscriber set for topic."""
        async with self._lock:
            self._subs.setdefault(topic, set()).add(ws)

    async def unsubscribe(self, ws: WebSocket, topic: str) -> None:
        """Remove ws from the subscriber set for topic."""
        async with self._lock:
            if topic in self._subs:
                self._subs[topic].discard(ws)

    async def disconnect(self, ws: WebSocket) -> None:
        """Remove ws from all topics (called on disconnect)."""
        async with self._lock:
            for subscribers in self._subs.values():
                subscribers.discard(ws)

    async def publish(self, topic: str, data: Any) -> None:
        """Send data to all subscribers of topic; silently drop dead connections."""
        message = {"topic": topic, "data": data}
        async with self._lock:
            subscribers = list(self._subs.get(topic, set()))
        for ws in subscribers:
            try:
                await ws.send_json(message)
            except Exception:
                logger.debug("Dead WebSocket removed from topic %s", topic)
                await self.disconnect(ws)

    async def close_all(self) -> None:
        """Close every open WebSocket and clear all subscriptions."""
        async with self._lock:
            sockets: set[WebSocket] = set()
            for subscribers in self._subs.values():
                sockets.update(subscribers)
            self._subs.clear()
        for ws in sockets:
            try:
                await ws.close()
            except Exception:
                # Silently ignore errors during shutdown - connections are already being torn down
                pass


# Module-level registry shared by the app
pubsub = PubSubRegistry()


async def heartbeat_loop(registry: PubSubRegistry, interval: float = 5.0) -> None:
    """Publish system:heartbeat every `interval` seconds until cancelled."""
    while True:
        await asyncio.sleep(interval)
        ts = datetime.now(tz=timezone.utc).isoformat()
        await registry.publish("system:heartbeat", {"ts": ts})


async def ws_endpoint(websocket: WebSocket) -> None:
    """Single /ws endpoint: authenticate via session cookie, then pub/sub loop."""
    from src.api.auth import get_session

    token = websocket.cookies.get("session")
    session = get_session(token) if token else None
    if session is None:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    await pubsub.subscribe(websocket, "system:heartbeat")

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except ValueError:
                await websocket.send_json({"op": "error", "message": "invalid JSON"})
                continue

            op = msg.get("op")
            if op == "subscribe":
                await pubsub.subscribe(websocket, msg.get("topic", ""))
            elif op == "unsubscribe":
                await pubsub.unsubscribe(websocket, msg.get("topic", ""))
            elif op == "ping":
                await websocket.send_json({"op": "pong"})
            else:
                await websocket.send_json({"op": "error", "message": f"unknown op: {op}"})
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.disconnect(websocket)
