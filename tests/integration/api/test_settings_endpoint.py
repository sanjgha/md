"""Integration tests for GET/PUT /api/settings."""


def test_get_settings_returns_seeded_defaults(authenticated_client, seeded_user, db_session):
    """GET returns settings rows present in DB for the user."""
    from src.db.models import UiSetting

    user, _ = seeded_user
    # Seed settings manually (migration seed won't run in test DB)
    for key, val in [("theme", "dark"), ("timezone", "America/New_York")]:
        db_session.add(UiSetting(user_id=user.id, key=key, value=val))
    db_session.commit()

    resp = authenticated_client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["theme"] == "dark"
    assert data["timezone"] == "America/New_York"


def test_get_settings_unauthenticated_returns_401(api_client):
    resp = api_client.get("/api/settings")
    assert resp.status_code == 401


def test_put_settings_upserts_theme(authenticated_client, seeded_user, db_session):
    from src.db.models import UiSetting

    user, _ = seeded_user
    db_session.add(UiSetting(user_id=user.id, key="theme", value="dark"))
    db_session.add(UiSetting(user_id=user.id, key="timezone", value="America/New_York"))
    db_session.commit()

    resp = authenticated_client.put("/api/settings", json={"theme": "light"})
    assert resp.status_code == 200
    assert resp.json()["theme"] == "light"
    assert resp.json()["timezone"] == "America/New_York"  # unchanged


def test_put_settings_second_update_replaces(authenticated_client, seeded_user, db_session):
    from src.db.models import UiSetting

    user, _ = seeded_user
    db_session.add(UiSetting(user_id=user.id, key="theme", value="dark"))
    db_session.add(UiSetting(user_id=user.id, key="timezone", value="America/New_York"))
    db_session.commit()

    authenticated_client.put("/api/settings", json={"theme": "light"})
    resp = authenticated_client.put("/api/settings", json={"theme": "dark"})
    assert resp.status_code == 200
    assert resp.json()["theme"] == "dark"


def test_put_settings_unknown_key_returns_422(authenticated_client, seeded_user):
    resp = authenticated_client.put("/api/settings", json={"badkey": "value"})
    assert resp.status_code == 422


def test_put_settings_invalid_theme_returns_422(authenticated_client, seeded_user):
    resp = authenticated_client.put("/api/settings", json={"theme": "purple"})
    assert resp.status_code == 422


def test_put_settings_unauthenticated_returns_401(api_client):
    resp = api_client.put("/api/settings", json={"theme": "dark"})
    assert resp.status_code == 401
