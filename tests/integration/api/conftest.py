"""Shared fixtures for API integration tests."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.api import auth as auth_module
from src.api import deps


def make_api_client(db_session: Session):
    """Create a TestClient with DB dependency overridden to testcontainers session."""
    # Import here to avoid circular issues before app is built
    from src.api.main import create_app

    app = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass  # cleanup handled by db_session fixture

    app.dependency_overrides[deps.get_db] = override_get_db
    return app, TestClient(app, raise_server_exceptions=True)


@pytest.fixture
def api_client(db_session: Session):
    """Yield a test client with real testcontainers DB; sessions cleared after each test."""
    auth_module.SESSIONS.clear()
    auth_module._rate_failures.clear()
    auth_module._lockouts.clear()
    app, client = make_api_client(db_session)
    with client as c:
        yield c
    app.dependency_overrides.clear()
    auth_module.SESSIONS.clear()


@pytest.fixture
def seeded_user(db_session: Session):
    """Insert a test user into the DB and return (user_obj, password)."""
    from src.api.auth import hash_password
    from src.db.models import User

    user = User(
        id=1,
        username="testuser",
        password_hash=hash_password("testpass123"),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user, "testpass123"


@pytest.fixture
def authenticated_client(api_client, seeded_user):
    """Get an API client with a valid session cookie."""
    user, password = seeded_user
    resp = api_client.post(
        "/api/auth/login", json={"username": user.username, "password": password}
    )
    assert resp.status_code == 200
    return api_client
