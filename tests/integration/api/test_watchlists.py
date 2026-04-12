"""Integration tests for watchlist CRUD API routes.

Tests cover:
- GET /api/watchlists - List all grouped by category
- POST /api/watchlists - Create new watchlist
- GET /api/watchlists/{id} - Get watchlist details
- PUT /api/watchlists/{id} - Update watchlist
- DELETE /api/watchlists/{id} - Delete watchlist

All endpoints require authentication and enforce user ownership.
"""

from src.db.models import (
    Stock,
    User,
    Watchlist,
    WatchlistCategory,
    WatchlistSymbol,
)


def test_get_watchlists_grouped_by_category(authenticated_client, seeded_user, db_session):
    """GET /api/watchlists returns watchlists grouped by category with symbol counts."""
    user, _ = seeded_user

    # Create default categories
    from src.api.watchlists.service import WatchlistService

    service = WatchlistService(db_session)
    categories = service.get_or_create_default_categories(user.id)

    # Create watchlists in different categories
    active_cat = [c for c in categories if c.name == "Active Trading"][0]
    research_cat = [c for c in categories if c.name == "Research"][0]

    watchlist1 = Watchlist(
        user_id=user.id,
        name="Day Trades",
        category_id=active_cat.id,
        is_auto_generated=False,
        watchlist_mode="static",
    )
    watchlist2 = Watchlist(
        user_id=user.id,
        name="Long Term Picks",
        category_id=research_cat.id,
        is_auto_generated=False,
        watchlist_mode="static",
    )
    db_session.add_all([watchlist1, watchlist2])
    db_session.commit()

    # Add symbols to first watchlist
    stock1 = Stock(symbol="AAPL", name="Apple Inc")
    stock2 = Stock(symbol="MSFT", name="Microsoft Corp")
    db_session.add_all([stock1, stock2])
    db_session.commit()

    symbol1 = WatchlistSymbol(watchlist_id=watchlist1.id, stock_id=stock1.id)
    symbol2 = WatchlistSymbol(watchlist_id=watchlist1.id, stock_id=stock2.id)
    db_session.add_all([symbol1, symbol2])
    db_session.commit()

    resp = authenticated_client.get("/api/watchlists")
    assert resp.status_code == 200
    data = resp.json()

    # Should have categories with watchlists
    assert len(data) > 0

    # Find Active Trading category
    active_category = next((c for c in data if c["category_name"] == "Active Trading"), None)
    assert active_category is not None
    assert active_category["category_icon"] == "🔥"
    assert active_category["is_system"] is True
    assert len(active_category["watchlists"]) == 1

    # Check watchlist data
    wl = active_category["watchlists"][0]
    assert wl["name"] == "Day Trades"
    assert wl["symbol_count"] == 2
    assert "id" in wl
    assert "created_at" in wl
    assert "updated_at" in wl


def test_get_watchlists_unauthenticated_returns_401(api_client):
    """GET /api/watchlists requires authentication."""
    resp = api_client.get("/api/watchlists")
    assert resp.status_code == 401


def test_create_watchlist(authenticated_client, seeded_user, db_session):
    """POST /api/watchlists creates a new watchlist."""
    user, _ = seeded_user

    # Create a category
    category = WatchlistCategory(
        user_id=user.id,
        name="Test Category",
        icon="🧪",
        is_system=False,
        sort_order=1,
    )
    db_session.add(category)
    db_session.commit()

    payload = {
        "name": "My New Watchlist",
        "category_id": category.id,
        "description": "Test description",
    }

    resp = authenticated_client.post("/api/watchlists", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    assert data["name"] == "My New Watchlist"
    assert data["category_id"] == category.id
    assert data["description"] == "Test description"
    assert data["is_auto_generated"] is False
    assert data["watchlist_mode"] == "static"
    assert "id" in data
    assert "created_at" in data


def test_create_watchlist_unauthenticated_returns_401(api_client, db_session):
    """POST /api/watchlists requires authentication."""
    resp = api_client.post("/api/watchlists", json={"name": "Test"})
    assert resp.status_code == 401


def test_create_watchlist_invalid_category_returns_400(authenticated_client, seeded_user):
    """POST /api/watchlists with invalid category_id returns 400."""
    user, _ = seeded_user

    payload = {
        "name": "Test Watchlist",
        "category_id": 99999,  # Non-existent category
    }

    resp = authenticated_client.post("/api/watchlists", json=payload)
    assert resp.status_code == 400


def test_get_watchlist_by_id(authenticated_client, seeded_user, db_session):
    """GET /api/watchlists/{id} returns watchlist details with symbols."""
    user, _ = seeded_user

    # Create watchlist
    watchlist = Watchlist(
        user_id=user.id,
        name="Tech Stocks",
        description="Technology companies",
        is_auto_generated=False,
        watchlist_mode="static",
    )
    db_session.add(watchlist)
    db_session.commit()

    # Add symbols
    stock1 = Stock(symbol="AAPL", name="Apple Inc")
    stock2 = Stock(symbol="GOOGL", name="Alphabet Inc")
    db_session.add_all([stock1, stock2])
    db_session.commit()

    symbol1 = WatchlistSymbol(
        watchlist_id=watchlist.id,
        stock_id=stock1.id,
        notes="Strong momentum",
        priority=1,
    )
    symbol2 = WatchlistSymbol(
        watchlist_id=watchlist.id,
        stock_id=stock2.id,
        notes="Breakout setup",
        priority=2,
    )
    db_session.add_all([symbol1, symbol2])
    db_session.commit()

    resp = authenticated_client.get(f"/api/watchlists/{watchlist.id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["id"] == watchlist.id
    assert data["name"] == "Tech Stocks"
    assert data["description"] == "Technology companies"
    assert len(data["symbols"]) == 2

    # Check symbol details
    symbols_by_stock = {s["stock_id"]: s for s in data["symbols"]}
    assert symbols_by_stock[stock1.id]["notes"] == "Strong momentum"
    assert symbols_by_stock[stock1.id]["priority"] == 1
    assert symbols_by_stock[stock2.id]["notes"] == "Breakout setup"
    assert symbols_by_stock[stock2.id]["priority"] == 2


def test_get_watchlist_unauthenticated_returns_401(api_client, db_session):
    """GET /api/watchlists/{id} requires authentication."""
    resp = api_client.get("/api/watchlists/1")
    assert resp.status_code == 401


def test_get_watchlist_not_owned_returns_404(authenticated_client, seeded_user, db_session):
    """GET /api/watchlists/{id} returns 404 for other users' watchlists."""
    user, _ = seeded_user

    # Create watchlist for user
    watchlist = Watchlist(
        user_id=user.id,
        name="Private Watchlist",
        is_auto_generated=False,
        watchlist_mode="static",
    )
    db_session.add(watchlist)
    db_session.commit()

    # Create another user
    from src.api.auth import hash_password

    other_user = User(
        id=2,
        username="otheruser",
        password_hash=hash_password("otherpass"),
    )
    db_session.add(other_user)
    db_session.commit()

    # Login as other user
    resp = authenticated_client.post(
        "/api/auth/login", json={"username": "otheruser", "password": "otherpass"}
    )
    assert resp.status_code == 200

    # Try to access first user's watchlist
    resp = authenticated_client.get(f"/api/watchlists/{watchlist.id}")
    assert resp.status_code == 404


def test_update_watchlist(authenticated_client, seeded_user, db_session):
    """PUT /api/watchlists/{id} updates watchlist fields."""
    user, _ = seeded_user

    # Create watchlist and category
    category1 = WatchlistCategory(
        user_id=user.id,
        name="Category 1",
        icon="📁",
        is_system=False,
        sort_order=1,
    )
    category2 = WatchlistCategory(
        user_id=user.id,
        name="Category 2",
        icon="📂",
        is_system=False,
        sort_order=2,
    )
    db_session.add_all([category1, category2])
    db_session.commit()

    watchlist = Watchlist(
        user_id=user.id,
        name="Old Name",
        category_id=category1.id,
        description="Old description",
        is_auto_generated=False,
        watchlist_mode="static",
    )
    db_session.add(watchlist)
    db_session.commit()

    # Update watchlist
    payload = {
        "name": "New Name",
        "category_id": category2.id,
        "description": "New description",
    }

    resp = authenticated_client.put(f"/api/watchlists/{watchlist.id}", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["id"] == watchlist.id
    assert data["name"] == "New Name"
    assert data["category_id"] == category2.id
    assert data["description"] == "New description"


def test_update_watchlist_partial_update(authenticated_client, seeded_user, db_session):
    """PUT /api/watchlists/{id} with partial fields updates only those fields."""
    user, _ = seeded_user

    watchlist = Watchlist(
        user_id=user.id,
        name="Original Name",
        description="Original description",
        is_auto_generated=False,
        watchlist_mode="static",
    )
    db_session.add(watchlist)
    db_session.commit()

    # Update only name
    payload = {"name": "Updated Name"}

    resp = authenticated_client.put(f"/api/watchlists/{watchlist.id}", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["name"] == "Updated Name"
    assert data["description"] == "Original description"  # Unchanged


def test_update_watchlist_unauthenticated_returns_401(api_client):
    """PUT /api/watchlists/{id} requires authentication."""
    resp = api_client.put("/api/watchlists/1", json={"name": "Test"})
    assert resp.status_code == 401


def test_update_watchlist_not_owned_returns_404(authenticated_client, seeded_user, db_session):
    """PUT /api/watchlists/{id} returns 404 for other users' watchlists."""
    user, _ = seeded_user

    watchlist = Watchlist(
        user_id=user.id,
        name="Private Watchlist",
        is_auto_generated=False,
        watchlist_mode="static",
    )
    db_session.add(watchlist)
    db_session.commit()

    # Create and login as other user
    from src.api.auth import hash_password

    other_user = User(
        id=2,
        username="otheruser",
        password_hash=hash_password("otherpass"),
    )
    db_session.add(other_user)
    db_session.commit()

    resp = authenticated_client.post(
        "/api/auth/login", json={"username": "otheruser", "password": "otherpass"}
    )
    assert resp.status_code == 200

    resp = authenticated_client.put(f"/api/watchlists/{watchlist.id}", json={"name": "Hacked"})
    assert resp.status_code == 404


def test_delete_watchlist(authenticated_client, seeded_user, db_session):
    """DELETE /api/watchlists/{id} deletes the watchlist."""
    user, _ = seeded_user

    watchlist = Watchlist(
        user_id=user.id,
        name="To Delete",
        is_auto_generated=False,
        watchlist_mode="static",
    )
    db_session.add(watchlist)
    db_session.commit()

    # Delete it
    resp = authenticated_client.delete(f"/api/watchlists/{watchlist.id}")
    assert resp.status_code == 204

    # Verify it's gone
    deleted = db_session.get(Watchlist, watchlist.id)
    assert deleted is None


def test_delete_watchlist_unauthenticated_returns_401(api_client):
    """DELETE /api/watchlists/{id} requires authentication."""
    resp = api_client.delete("/api/watchlists/1")
    assert resp.status_code == 401


def test_delete_watchlist_not_owned_returns_404(authenticated_client, seeded_user, db_session):
    """DELETE /api/watchlists/{id} returns 404 for other users' watchlists."""
    user, _ = seeded_user

    watchlist = Watchlist(
        user_id=user.id,
        name="Private Watchlist",
        is_auto_generated=False,
        watchlist_mode="static",
    )
    db_session.add(watchlist)
    db_session.commit()

    # Create and login as other user
    from src.api.auth import hash_password

    other_user = User(
        id=2,
        username="otheruser",
        password_hash=hash_password("otherpass"),
    )
    db_session.add(other_user)
    db_session.commit()

    resp = authenticated_client.post(
        "/api/auth/login", json={"username": "otheruser", "password": "otherpass"}
    )
    assert resp.status_code == 200

    resp = authenticated_client.delete(f"/api/watchlists/{watchlist.id}")
    assert resp.status_code == 404

    # Verify original watchlist still exists
    still_exists = db_session.get(Watchlist, watchlist.id)
    assert still_exists is not None
