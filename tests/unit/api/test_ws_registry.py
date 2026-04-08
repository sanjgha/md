"""Unit tests for PubSubRegistry in src/api/ws.py."""

from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def registry():
    from src.api.ws import PubSubRegistry

    return PubSubRegistry()


@pytest.mark.asyncio
async def test_subscribe_and_publish(registry):
    ws = AsyncMock()
    await registry.subscribe(ws, "test:topic")
    await registry.publish("test:topic", {"msg": "hello"})
    ws.send_json.assert_called_once_with({"topic": "test:topic", "data": {"msg": "hello"}})


@pytest.mark.asyncio
async def test_unsubscribe_stops_delivery(registry):
    ws = AsyncMock()
    await registry.subscribe(ws, "test:topic")
    await registry.unsubscribe(ws, "test:topic")
    await registry.publish("test:topic", {"msg": "hello"})
    ws.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_disconnect_removes_from_all_topics(registry):
    ws = AsyncMock()
    await registry.subscribe(ws, "t1")
    await registry.subscribe(ws, "t2")
    await registry.disconnect(ws)
    await registry.publish("t1", {})
    await registry.publish("t2", {})
    ws.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_publish_skips_dead_connection(registry):
    ws = AsyncMock()
    ws.send_json.side_effect = Exception("connection closed")
    await registry.subscribe(ws, "test:topic")
    # Should not raise
    await registry.publish("test:topic", {})
