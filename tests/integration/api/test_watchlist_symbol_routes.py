"""Integration tests for watchlist symbol management API routes.

Tests the following endpoints:
- GET /api/watchlists/{id}/symbols - List symbols
- POST /api/watchlists/{id}/symbols - Add symbol
- DELETE /api/watchlists/{id}/symbols/{symbol} - Remove symbol
"""

import pytest
from sqlalchemy.orm import Session


@pytest.fixture
def test_data(db_session: Session, seeded_user):
    """Create test data: categories, watchlists, and stocks.

    seeded_user fixture provides the user (id=1).
    """
    from src.db.models import WatchlistCategory, Watchlist, Stock

    # Create category
    category = WatchlistCategory(
        id=1,
        user_id=1,
        name="Test Category",
        icon="🧪",
        is_system=False,
        sort_order=1,
    )
    db_session.add(category)

    # Create watchlists
    watchlist1 = Watchlist(
        id=1,
        user_id=1,
        name="Tech Stocks",
        category_id=1,
        description="Technology stocks",
        is_auto_generated=False,
        watchlist_mode="static",
    )
    db_session.add(watchlist1)

    watchlist2 = Watchlist(
        id=2,
        user_id=1,
        name="Finance Stocks",
        category_id=1,
        description="Finance stocks",
        is_auto_generated=False,
        watchlist_mode="static",
    )
    db_session.add(watchlist2)

    # Create stocks
    stocks = [
        Stock(id=1, symbol="AAPL", name="Apple Inc."),
        Stock(id=2, symbol="MSFT", name="Microsoft Corp."),
        Stock(id=3, symbol="GOOGL", name="Alphabet Inc."),
        Stock(id=4, symbol="TSLA", name="Tesla Inc."),
    ]
    for stock in stocks:
        db_session.add(stock)

    db_session.commit()

    return {
        "category": category,
        "watchlist1": watchlist1,
        "watchlist2": watchlist2,
        "stocks": stocks,
    }


class TestListSymbols:
    """Tests for GET /api/watchlists/{id}/symbols"""

    def test_list_symbols_empty(self, authenticated_client, test_data):
        """Test listing symbols from an empty watchlist."""
        response = authenticated_client.get("/api/watchlists/1/symbols")

        assert response.status_code == 200
        data = response.json()
        assert "symbols" in data
        assert len(data["symbols"]) == 0

    def test_list_symbols_with_items(self, authenticated_client, test_data, db_session):
        """Test listing symbols from a watchlist with symbols."""
        from src.api.watchlists.service import WatchlistService

        # Add symbols using the service
        service = WatchlistService(db_session)
        service.add_symbol(1, 1, "AAPL", notes="Great company")
        service.add_symbol(1, 1, "MSFT")
        service.add_symbol(1, 1, "GOOGL", notes="Buy low")

        response = authenticated_client.get("/api/watchlists/1/symbols")

        assert response.status_code == 200
        data = response.json()
        assert "symbols" in data
        assert len(data["symbols"]) == 3

        # Verify symbol data structure
        symbol = data["symbols"][0]
        assert "id" in symbol
        assert "stock_id" in symbol
        assert "symbol" in symbol
        assert "name" in symbol
        assert "notes" in symbol
        assert "added_at" in symbol

    def test_list_symbols_unauthorized_watchlist(self, authenticated_client, test_data):
        """Test listing symbols from a non-existent watchlist."""
        response = authenticated_client.get("/api/watchlists/999/symbols")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


class TestAddSymbol:
    """Tests for POST /api/watchlists/{id}/symbols"""

    def test_add_symbol_success(self, authenticated_client, test_data):
        """Test successfully adding a symbol to a watchlist."""
        payload = {"symbol": "AAPL", "notes": "Great tech stock"}

        response = authenticated_client.post(
            "/api/watchlists/1/symbols",
            json=payload,
        )

        assert response.status_code == 201
        data = response.json()
        assert "message" in data
        assert "symbol" in data
        assert data["symbol"]["symbol"] == "AAPL"
        assert data["symbol"]["notes"] == "Great tech stock"

    def test_add_symbol_without_notes(self, authenticated_client, test_data):
        """Test adding a symbol without notes."""
        payload = {"symbol": "MSFT"}

        response = authenticated_client.post(
            "/api/watchlists/1/symbols",
            json=payload,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["symbol"]["symbol"] == "MSFT"
        assert data["symbol"]["notes"] is None

    def test_add_symbol_duplicate(self, authenticated_client, test_data, db_session):
        """Test adding a duplicate symbol fails."""
        from src.api.watchlists.service import WatchlistService

        # Add symbol first time
        service = WatchlistService(db_session)
        service.add_symbol(1, 1, "AAPL")

        # Try to add again
        payload = {"symbol": "AAPL"}

        response = authenticated_client.post(
            "/api/watchlists/1/symbols",
            json=payload,
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "already exists" in data["detail"].lower()

    def test_add_symbol_nonexistent_stock(self, authenticated_client, test_data):
        """Test adding a symbol that doesn't exist in stocks table."""
        payload = {"symbol": "NOTFOUND"}

        response = authenticated_client.post(
            "/api/watchlists/1/symbols",
            json=payload,
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_add_symbol_unauthorized_watchlist(self, authenticated_client, test_data):
        """Test adding a symbol to a non-existent watchlist."""
        payload = {"symbol": "AAPL"}

        response = authenticated_client.post(
            "/api/watchlists/999/symbols",
            json=payload,
        )

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_add_symbol_missing_symbol_field(self, authenticated_client, test_data):
        """Test adding a symbol without providing the symbol field."""
        payload = {"notes": "Missing symbol"}

        response = authenticated_client.post(
            "/api/watchlists/1/symbols",
            json=payload,
        )

        assert response.status_code == 422  # Validation error


class TestRemoveSymbol:
    """Tests for DELETE /api/watchlists/{id}/symbols/{symbol}"""

    def test_remove_symbol_success(self, authenticated_client, test_data, db_session):
        """Test successfully removing a symbol from a watchlist."""
        from src.api.watchlists.service import WatchlistService

        # Add symbol first
        service = WatchlistService(db_session)
        service.add_symbol(1, 1, "AAPL", notes="Will be removed")

        # Remove it
        response = authenticated_client.delete("/api/watchlists/1/symbols/AAPL")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "removed" in data["message"].lower() or "success" in data["message"].lower()

    def test_remove_symbol_not_found(self, authenticated_client, test_data):
        """Test removing a symbol that's not in the watchlist."""
        response = authenticated_client.delete("/api/watchlists/1/symbols/AAPL")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_remove_symbol_unauthorized_watchlist(self, authenticated_client, test_data):
        """Test removing a symbol from a non-existent watchlist."""
        response = authenticated_client.delete("/api/watchlists/999/symbols/AAPL")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data

    def test_remove_symbol_nonexistent_stock(self, authenticated_client, test_data):
        """Test removing a symbol that doesn't exist in stocks table."""
        response = authenticated_client.delete("/api/watchlists/1/symbols/NONEXISTENT")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


class TestSymbolCasing:
    """Test symbol case handling"""

    def test_add_symbol_lowercase(self, authenticated_client, test_data):
        """Test that lowercase symbols are converted to uppercase."""
        payload = {"symbol": "aapl", "notes": "Lowercase test"}

        response = authenticated_client.post(
            "/api/watchlists/1/symbols",
            json=payload,
        )

        assert response.status_code == 201
        data = response.json()
        # Should be stored and returned as uppercase
        assert data["symbol"]["symbol"] == "AAPL"

    def test_remove_symbol_lowercase(self, authenticated_client, test_data, db_session):
        """Test that lowercase symbol in DELETE works."""
        from src.api.watchlists.service import WatchlistService

        # Add with uppercase
        service = WatchlistService(db_session)
        service.add_symbol(1, 1, "AAPL")

        # Remove with lowercase
        response = authenticated_client.delete("/api/watchlists/1/symbols/aapl")

        assert response.status_code == 200
