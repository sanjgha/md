"""Integration tests for watchlist categories and clone API endpoints."""

import pytest
from sqlalchemy.orm import Session


@pytest.fixture
def seeded_watchlist_data(db_session: Session, seeded_user):
    """Seed watchlists and categories for testing."""
    from src.db.models import Watchlist, WatchlistCategory, WatchlistSymbol, Stock

    user, _ = seeded_user

    # Create categories
    cat1 = WatchlistCategory(
        user_id=user.id,
        name="Active Trading",
        icon="🔥",
        is_system=True,
        sort_order=1,
    )
    cat2 = WatchlistCategory(
        user_id=user.id,
        name="Research",
        icon="🔬",
        is_system=True,
        sort_order=2,
    )
    cat3 = WatchlistCategory(
        user_id=user.id,
        name="Custom Category",
        icon="⭐",
        is_system=False,
        sort_order=3,
    )
    db_session.add_all([cat1, cat2, cat3])
    db_session.commit()

    # Create stocks
    stock1 = Stock(symbol="AAPL", name="Apple Inc.")
    stock2 = Stock(symbol="MSFT", name="Microsoft Corp.")
    stock3 = Stock(symbol="GOOGL", name="Alphabet Inc.")
    db_session.add_all([stock1, stock2, stock3])
    db_session.commit()

    # Create watchlist with symbols
    watchlist1 = Watchlist(
        user_id=user.id,
        name="Tech Stocks",
        category_id=cat1.id,
        description="Big tech companies",
    )
    db_session.add(watchlist1)
    db_session.commit()

    # Add symbols to watchlist
    symbol1 = WatchlistSymbol(
        watchlist_id=watchlist1.id,
        stock_id=stock1.id,
        notes="Strong buy",
        priority=1,
    )
    symbol2 = WatchlistSymbol(
        watchlist_id=watchlist1.id,
        stock_id=stock2.id,
        notes="Hold",
        priority=2,
    )
    db_session.add_all([symbol1, symbol2])
    db_session.commit()

    return {
        "user": user,
        "categories": [cat1, cat2, cat3],
        "watchlists": [watchlist1],
        "stocks": [stock1, stock2, stock3],
    }


# ========== GET /api/watchlists/categories ==========


def test_get_categories_returns_all_user_categories(authenticated_client, seeded_watchlist_data):
    """GET /api/watchlists/categories returns all categories for authenticated user."""
    resp = authenticated_client.get("/api/watchlists/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 3

    # Check categories are ordered by sort_order
    assert data[0]["name"] == "Active Trading"
    assert data[1]["name"] == "Research"
    assert data[2]["name"] == "Custom Category"

    # Check category structure
    category = data[0]
    assert "id" in category
    assert "name" in category
    assert "description" in category
    assert "color" in category
    assert "icon" in category
    assert "created_at" in category
    assert "updated_at" in category


def test_get_categories_unauthenticated_returns_401(api_client):
    """GET /api/watchlists/categories returns 401 for unauthenticated requests."""
    resp = api_client.get("/api/watchlists/categories")
    assert resp.status_code == 401


def test_get_categories_empty_returns_empty_list(authenticated_client, seeded_user):
    """GET /api/watchlists/categories returns empty list when no categories exist."""
    # Create user without categories (user_id=1, no categories seeded)
    resp = authenticated_client.get("/api/watchlists/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 0


# ========== POST /api/watchlists/categories ==========


def test_create_category_with_minimal_fields(authenticated_client, seeded_user):
    """POST /api/watchlists/categories creates category with only required fields."""
    resp = authenticated_client.post(
        "/api/watchlists/categories",
        json={"name": "My Category"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Category"
    assert data["description"] is None
    assert data["color"] is None
    assert data["icon"] is None
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_create_category_with_all_fields(authenticated_client, seeded_user):
    """POST /api/watchlists/categories creates category with all optional fields."""
    resp = authenticated_client.post(
        "/api/watchlists/categories",
        json={
            "name": "Momentum Plays",
            "description": "High momentum stocks",
            "color": "#FF5733",
            "icon": "🚀",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Momentum Plays"
    assert data["description"] == "High momentum stocks"
    assert data["color"] == "#FF5733"
    assert data["icon"] == "🚀"


def test_create_category_unauthenticated_returns_401(api_client):
    """POST /api/watchlists/categories returns 401 for unauthenticated requests."""
    resp = api_client.post(
        "/api/watchlists/categories",
        json={"name": "Test Category"},
    )
    assert resp.status_code == 401


def test_create_category_duplicate_name_returns_400(authenticated_client, seeded_watchlist_data):
    """POST /api/watchlists/categories returns 400 for duplicate category name."""
    # Try to create category with same name as existing one
    resp = authenticated_client.post(
        "/api/watchlists/categories",
        json={"name": "Active Trading"},  # Already exists
    )
    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"].lower()


def test_create_category_invalid_name_returns_422(authenticated_client, seeded_user):
    """POST /api/watchlists/categories returns 422 for invalid name."""
    resp = authenticated_client.post(
        "/api/watchlists/categories",
        json={"name": ""},  # Empty name
    )
    assert resp.status_code == 422


# ========== DELETE /api/watchlists/categories/{id} ==========


def test_delete_category_custom_succeeds(authenticated_client, seeded_watchlist_data):
    """DELETE /api/watchlists/categories/{id} deletes custom (non-system) category."""
    categories = seeded_watchlist_data["categories"]
    custom_category = categories[2]  # "Custom Category" (is_system=False)

    resp = authenticated_client.delete(f"/api/watchlists/categories/{custom_category.id}")
    assert resp.status_code == 200

    # Verify category is deleted
    resp = authenticated_client.get("/api/watchlists/categories")
    data = resp.json()
    assert len(data) == 2  # Only 2 system categories remain
    assert all(cat["name"] != "Custom Category" for cat in data)


def test_delete_category_system_returns_403(authenticated_client, seeded_watchlist_data):
    """DELETE /api/watchlists/categories/{id} returns 403 for system categories."""
    categories = seeded_watchlist_data["categories"]
    system_category = categories[0]  # "Active Trading" (is_system=True)

    resp = authenticated_client.delete(f"/api/watchlists/categories/{system_category.id}")
    assert resp.status_code == 403
    assert "system categories" in resp.json()["detail"].lower()

    # Verify system category still exists
    resp = authenticated_client.get("/api/watchlists/categories")
    data = resp.json()
    assert len(data) == 3
    assert any(cat["name"] == "Active Trading" for cat in data)


def test_delete_category_not_found_returns_404(authenticated_client, seeded_user):
    """DELETE /api/watchlists/categories/{id} returns 404 for non-existent category."""
    resp = authenticated_client.delete("/api/watchlists/categories/99999")
    assert resp.status_code == 404


def test_delete_category_unauthenticated_returns_401(api_client):
    """DELETE /api/watchlists/categories/{id} returns 401 for unauthenticated requests."""
    resp = api_client.delete("/api/watchlists/categories/1")
    assert resp.status_code == 401


def test_delete_category_different_user_returns_404(
    authenticated_client, seeded_watchlist_data, db_session
):
    """DELETE /api/watchlists/categories/{id} returns 404 for category owned by different user."""
    from src.api.auth import hash_password
    from src.db.models import User, WatchlistCategory

    # Create another user with a category
    other_user = User(id=2, username="otheruser", password_hash=hash_password("pass123"))
    db_session.add(other_user)

    other_category = WatchlistCategory(
        user_id=other_user.id,
        name="Other User Category",
        icon="🔒",
        is_system=False,
    )
    db_session.add(other_category)
    db_session.commit()

    # Try to delete other user's category
    resp = authenticated_client.delete(f"/api/watchlists/categories/{other_category.id}")
    assert resp.status_code == 404


# ========== POST /api/watchlists/{id}/clone ==========


def test_clone_watchlist_succeeds(authenticated_client, seeded_watchlist_data):
    """POST /api/watchlists/{id}/clone creates a copy with all symbols."""
    watchlists = seeded_watchlist_data["watchlists"]
    original_watchlist = watchlists[0]

    resp = authenticated_client.post(
        f"/api/watchlists/{original_watchlist.id}/clone",
        json={"name": "Tech Stocks Copy"},
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Tech Stocks Copy"
    assert data["id"] != original_watchlist.id  # Different ID
    assert data["description"] == original_watchlist.description
    assert data["category_id"] == original_watchlist.category_id
    assert data["is_auto_generated"] is False  # Clones are never auto-generated
    assert len(data["symbols"]) == 2  # All symbols copied

    # Verify symbols were copied correctly
    symbols = data["symbols"]
    assert symbols[0]["notes"] == "Strong buy"
    assert symbols[0]["priority"] == 1
    assert symbols[1]["notes"] == "Hold"
    assert symbols[1]["priority"] == 2


def test_clone_watchlist_with_custom_category_and_description(
    authenticated_client, seeded_watchlist_data
):
    """POST /api/watchlists/{id}/clone can override category and description."""
    watchlists = seeded_watchlist_data["watchlists"]
    original_watchlist = watchlists[0]
    categories = seeded_watchlist_data["categories"]
    new_category = categories[1]  # "Research" category

    resp = authenticated_client.post(
        f"/api/watchlists/{original_watchlist.id}/clone",
        json={
            "name": "Research Copy",
            "category_id": new_category.id,
            "description": "For research purposes",
        },
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Research Copy"
    assert data["category_id"] == new_category.id
    assert data["description"] == "For research purposes"
    assert len(data["symbols"]) == 2


def test_clone_watchlist_unauthenticated_returns_401(api_client):
    """POST /api/watchlists/{id}/clone returns 401 for unauthenticated requests."""
    resp = api_client.post("/api/watchlists/1/clone", json={"name": "Copy"})
    assert resp.status_code == 401


def test_clone_watchlist_not_found_returns_404(authenticated_client, seeded_user):
    """POST /api/watchlists/{id}/clone returns 404 for non-existent watchlist."""
    resp = authenticated_client.post("/api/watchlists/99999/clone", json={"name": "Copy"})
    assert resp.status_code == 404


def test_clone_watchlist_different_user_returns_404(
    authenticated_client, seeded_watchlist_data, db_session
):
    """POST /api/watchlists/{id}/clone returns 404 for watchlist owned by different user."""
    from src.api.auth import hash_password
    from src.db.models import User, Watchlist

    # Create another user with a watchlist
    other_user = User(id=2, username="otheruser", password_hash=hash_password("pass123"))
    db_session.add(other_user)

    other_watchlist = Watchlist(
        user_id=other_user.id,
        name="Other User Watchlist",
    )
    db_session.add(other_watchlist)
    db_session.commit()

    # Try to clone other user's watchlist
    resp = authenticated_client.post(
        f"/api/watchlists/{other_watchlist.id}/clone",
        json={"name": "Stolen Copy"},
    )
    assert resp.status_code == 404


def test_clone_watchlist_duplicate_name_returns_400(authenticated_client, seeded_watchlist_data):
    """POST /api/watchlists/{id}/clone returns 400 if name already exists for user."""
    watchlists = seeded_watchlist_data["watchlists"]
    original_watchlist = watchlists[0]

    # Try to clone with the same name as the original
    resp = authenticated_client.post(
        f"/api/watchlists/{original_watchlist.id}/clone",
        json={"name": original_watchlist.name},  # "Tech Stocks" already exists
    )

    assert resp.status_code == 400
    assert "already exists" in resp.json()["detail"].lower()


def test_clone_watchlist_invalid_name_returns_422(authenticated_client, seeded_watchlist_data):
    """POST /api/watchlists/{id}/clone returns 422 for invalid name."""
    watchlists = seeded_watchlist_data["watchlists"]
    original_watchlist = watchlists[0]

    resp = authenticated_client.post(
        f"/api/watchlists/{original_watchlist.id}/clone",
        json={"name": ""},  # Empty name
    )

    assert resp.status_code == 422


def test_clone_watchlist_empty_watchlist_succeeds(authenticated_client, seeded_user, db_session):
    """POST /api/watchlists/{id}/clone successfully clones empty watchlist."""
    from src.db.models import Watchlist

    user, _ = seeded_user

    # Create empty watchlist
    empty_watchlist = Watchlist(
        user_id=user.id,
        name="Empty List",
    )
    db_session.add(empty_watchlist)
    db_session.commit()

    resp = authenticated_client.post(
        f"/api/watchlists/{empty_watchlist.id}/clone",
        json={"name": "Empty Copy"},
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Empty Copy"
    assert len(data["symbols"]) == 0


def test_clone_watchlist_with_other_users_category_returns_400(
    authenticated_client, seeded_watchlist_data, db_session
):
    """POST /api/watchlists/{id}/clone returns 400 when category_id belongs to another user."""
    from src.api.auth import hash_password
    from src.db.models import User, WatchlistCategory

    watchlists = seeded_watchlist_data["watchlists"]
    original_watchlist = watchlists[0]

    # Create another user with their own category
    other_user = User(id=99, username="otheruser2", password_hash=hash_password("pass123"))
    db_session.add(other_user)
    other_cat = WatchlistCategory(
        user_id=other_user.id,
        name="Private Category",
        is_system=False,
        sort_order=1,
    )
    db_session.add(other_cat)
    db_session.commit()

    # Try to clone and assign to another user's category
    resp = authenticated_client.post(
        f"/api/watchlists/{original_watchlist.id}/clone",
        json={"name": "Stolen Clone", "category_id": other_cat.id},
    )
    assert resp.status_code == 400
    assert "invalid category_id" in resp.json()["detail"].lower()


def test_get_categories_response_includes_is_system_and_sort_order(
    authenticated_client, seeded_watchlist_data
):
    """GET /api/watchlists/categories includes is_system and sort_order fields."""
    resp = authenticated_client.get("/api/watchlists/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0

    # All categories must expose is_system and sort_order
    for cat in data:
        assert "is_system" in cat, "CategoryResponse must include is_system"
        assert "sort_order" in cat, "CategoryResponse must include sort_order"

    # Verify values are correct for known categories
    active = next(c for c in data if c["name"] == "Active Trading")
    assert active["is_system"] is True
    assert active["sort_order"] == 1

    custom = next(c for c in data if c["name"] == "Custom Category")
    assert custom["is_system"] is False
    assert custom["sort_order"] == 3
