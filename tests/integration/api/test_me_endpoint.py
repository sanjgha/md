"""Integration tests for GET /api/me."""


def test_me_returns_user_when_authenticated(authenticated_client, seeded_user):
    user, _ = seeded_user
    resp = authenticated_client.get("/api/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == user.id
    assert data["username"] == user.username


def test_me_returns_401_when_unauthenticated(api_client):
    resp = api_client.get("/api/me")
    assert resp.status_code == 401
