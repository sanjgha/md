"""Integration tests for the /ws endpoint."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.api import deps


def make_authed_client(db_session: Session, heartbeat_interval: str = "5.0"):
    """Build a fresh TestClient with the given HEARTBEAT_INTERVAL already set."""
    os.environ["HEARTBEAT_INTERVAL"] = heartbeat_interval
    from src.api.main import create_app

    app = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[deps.get_db] = override_get_db
    return app, TestClient(app, raise_server_exceptions=True)


def test_ws_rejects_unauthenticated(api_client):
    with pytest.raises(Exception):
        with api_client.websocket_connect("/ws") as ws:
            ws.receive_json()  # should not reach here — closed 1008


def test_ws_accepts_authenticated_and_receives_heartbeat(db_session, seeded_user, monkeypatch):
    # Set a fast heartbeat interval BEFORE the app/lifespan starts
    monkeypatch.setenv("HEARTBEAT_INTERVAL", "0.1")
    user, password = seeded_user
    app, client = make_authed_client(db_session, heartbeat_interval="0.1")
    with client as c:
        resp = c.post("/api/auth/login", json={"username": user.username, "password": password})
        assert resp.status_code == 200
        with c.websocket_connect("/ws") as ws:
            msg = ws.receive_json()
            assert msg["topic"] == "system:heartbeat"
    app.dependency_overrides.clear()


def test_ws_ping_pong(authenticated_client):
    with authenticated_client.websocket_connect("/ws") as ws:
        ws.send_json({"op": "ping"})
        msg = ws.receive_json()
        assert msg == {"op": "pong"}
