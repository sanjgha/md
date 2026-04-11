"""Integration tests for POST /api/auth/login and /api/auth/logout."""


def test_login_correct_credentials_returns_200_and_cookie(api_client, seeded_user):
    user, password = seeded_user
    resp = api_client.post(
        "/api/auth/login", json={"username": user.username, "password": password}
    )
    assert resp.status_code == 200
    assert "session" in resp.cookies


def test_login_wrong_password_returns_401(api_client, seeded_user):
    user, _ = seeded_user
    resp = api_client.post("/api/auth/login", json={"username": user.username, "password": "wrong"})
    assert resp.status_code == 401
    assert "session" not in resp.cookies


def test_login_unknown_user_returns_401(api_client):
    resp = api_client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
    assert resp.status_code == 401


def test_logout_invalidates_session(authenticated_client):
    # confirm we're authenticated
    assert authenticated_client.get("/api/me").status_code == 200
    resp = authenticated_client.post("/api/auth/logout")
    assert resp.status_code == 200
    # session cookie cleared — subsequent request should 401
    assert authenticated_client.get("/api/me").status_code == 401


def test_login_rate_limit_triggers_after_5_failures(api_client, seeded_user):
    from src.api.auth import _lockouts, _rate_failures

    _rate_failures.clear()
    _lockouts.clear()

    user, _ = seeded_user
    for _ in range(5):
        api_client.post("/api/auth/login", json={"username": user.username, "password": "bad"})

    resp = api_client.post("/api/auth/login", json={"username": user.username, "password": "bad"})
    assert resp.status_code == 429
