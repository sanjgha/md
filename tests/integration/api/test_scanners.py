"""Integration tests for scanner API endpoints."""


def test_list_scanners_returns_registered_scanners(authenticated_client):
    """GET /api/scanners returns all registered scanners with metadata."""
    resp = authenticated_client.get("/api/scanners")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 3

    names = {s["name"] for s in data}
    assert "momentum" in names
    assert "price_action" in names
    assert "volume" in names

    for scanner in data:
        assert "name" in scanner
        assert "timeframe" in scanner
        assert "description" in scanner
        assert scanner["timeframe"] == "daily"


def test_list_scanners_requires_auth(api_client):
    """GET /api/scanners returns 401 without authentication."""
    resp = api_client.get("/api/scanners")
    assert resp.status_code == 401
