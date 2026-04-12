"""Unit tests for watchlist Pydantic schemas."""

from datetime import datetime
import pytest
from pydantic import ValidationError


class TestWatchlistCreateSchema:
    """Test WatchlistCreate schema validation."""

    def test_watchlist_create_schema(self):
        """Test that WatchlistCreate validates name is required."""
        from src.api.watchlists.schemas import WatchlistCreate

        # Valid watchlist
        data = {"name": "My Watchlist"}
        watchlist = WatchlistCreate(**data)
        assert watchlist.name == "My Watchlist"

        # Missing name should fail
        with pytest.raises(ValidationError) as exc_info:
            WatchlistCreate()
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("name",) and e["type"] == "missing" for e in errors)

    def test_watchlist_create_with_optional_fields(self):
        """Test WatchlistCreate with optional fields."""
        from src.api.watchlists.schemas import WatchlistCreate

        data = {
            "name": "Tech Stocks",
            "category_id": 1,
            "description": "Technology companies to watch",
        }
        watchlist = WatchlistCreate(**data)
        assert watchlist.name == "Tech Stocks"
        assert watchlist.category_id == 1
        assert watchlist.description == "Technology companies to watch"


class TestWatchlistUpdateSchema:
    """Test WatchlistUpdate schema validation."""

    def test_watchlist_update_all_fields(self):
        """Test WatchlistUpdate with all fields."""
        from src.api.watchlists.schemas import WatchlistUpdate

        data = {
            "name": "Updated Watchlist",
            "category_id": 2,
            "description": "Updated description",
        }
        watchlist = WatchlistUpdate(**data)
        assert watchlist.name == "Updated Watchlist"
        assert watchlist.category_id == 2
        assert watchlist.description == "Updated description"

    def test_watchlist_update_partial(self):
        """Test WatchlistUpdate with partial data."""
        from src.api.watchlists.schemas import WatchlistUpdate

        # Only name
        watchlist = WatchlistUpdate(name="New Name")
        assert watchlist.name == "New Name"
        assert watchlist.category_id is None
        assert watchlist.description is None


class TestWatchlistSymbolCreateSchema:
    """Test WatchlistSymbolCreate schema validation."""

    def test_watchlist_symbol_create_required_fields(self):
        """Test WatchlistSymbolCreate with required fields."""
        from src.api.watchlists.schemas import WatchlistSymbolCreate

        data = {"stock_id": 123}
        symbol = WatchlistSymbolCreate(**data)
        assert symbol.stock_id == 123
        assert symbol.notes is None
        assert symbol.priority == 0

    def test_watchlist_symbol_create_with_optional_fields(self):
        """Test WatchlistSymbolCreate with optional fields."""
        from src.api.watchlists.schemas import WatchlistSymbolCreate

        data = {
            "stock_id": 456,
            "notes": "Strong momentum",
            "priority": 5,
        }
        symbol = WatchlistSymbolCreate(**data)
        assert symbol.stock_id == 456
        assert symbol.notes == "Strong momentum"
        assert symbol.priority == 5


class TestWatchlistSymbolResponseSchema:
    """Test WatchlistSymbolResponse schema validation."""

    def test_watchlist_symbol_response_from_attributes(self):
        """Test WatchlistSymbolResponse with from_attributes."""
        from src.api.watchlists.schemas import WatchlistSymbolResponse

        # Mock object with attributes
        class MockSymbol:
            id = 1
            stock_id = 123
            notes = "Test notes"
            priority = 3
            added_at = datetime.now()

        mock = MockSymbol()
        response = WatchlistSymbolResponse.model_validate(mock)

        assert response.id == 1
        assert response.stock_id == 123
        assert response.notes == "Test notes"
        assert response.priority == 3


class TestWatchlistResponseSchema:
    """Test WatchlistResponse schema validation."""

    def test_watchlist_response_from_attributes(self):
        """Test WatchlistResponse with from_attributes."""
        from src.api.watchlists.schemas import WatchlistResponse

        # Mock object with attributes
        class MockWatchlist:
            id = 1
            name = "Test Watchlist"
            category_id = 5
            description = "Test description"
            is_auto_generated = False
            scanner_name = None
            watchlist_mode = "static"
            source_scan_date = None
            created_at = datetime.now()
            updated_at = datetime.now()
            symbols = []

        mock = MockWatchlist()
        response = WatchlistResponse.model_validate(mock)

        assert response.id == 1
        assert response.name == "Test Watchlist"
        assert response.category_id == 5
        assert response.description == "Test description"
        assert response.is_auto_generated is False
        assert response.watchlist_mode == "static"


class TestCategoryCreateSchema:
    """Test CategoryCreate schema validation."""

    def test_category_create_required_fields(self):
        """Test CategoryCreate with required fields."""
        from src.api.watchlists.schemas import CategoryCreate

        data = {"name": "Growth Stocks"}
        category = CategoryCreate(**data)
        assert category.name == "Growth Stocks"
        assert category.description is None
        assert category.color is None
        assert category.icon is None

    def test_category_create_with_optional_fields(self):
        """Test CategoryCreate with optional fields."""
        from src.api.watchlists.schemas import CategoryCreate

        data = {
            "name": "Value Stocks",
            "description": "Undervalued companies",
            "color": "#FF5733",
            "icon": "chart-line",
        }
        category = CategoryCreate(**data)
        assert category.name == "Value Stocks"
        assert category.description == "Undervalued companies"
        assert category.color == "#FF5733"
        assert category.icon == "chart-line"


class TestCategoryUpdateSchema:
    """Test CategoryUpdate schema validation."""

    def test_category_update_all_fields(self):
        """Test CategoryUpdate with all fields."""
        from src.api.watchlists.schemas import CategoryUpdate

        data = {
            "name": "Updated Category",
            "description": "Updated description",
            "color": "#00FF00",
            "icon": "star",
        }
        category = CategoryUpdate(**data)
        assert category.name == "Updated Category"
        assert category.description == "Updated description"
        assert category.color == "#00FF00"
        assert category.icon == "star"


class TestCategoryResponseSchema:
    """Test CategoryResponse schema validation."""

    def test_category_response_from_attributes(self):
        """Test CategoryResponse with from_attributes."""
        from src.api.watchlists.schemas import CategoryResponse

        # Mock object with attributes
        class MockCategory:
            id = 1
            name = "Test Category"
            description = "Test description"
            color = "#123456"
            icon = "test-icon"
            created_at = datetime.now()
            updated_at = datetime.now()

        mock = MockCategory()
        response = CategoryResponse.model_validate(mock)

        assert response.id == 1
        assert response.name == "Test Category"
        assert response.description == "Test description"
        assert response.color == "#123456"
        assert response.icon == "test-icon"


class TestWatchlistListResponseSchema:
    """Test WatchlistListResponse schema validation."""

    def test_watchlist_list_response(self):
        """Test WatchlistListResponse with list of watchlists."""
        from src.api.watchlists.schemas import WatchlistListResponse

        class MockWatchlist:
            id = 1
            name = "Watchlist 1"
            category_id = None
            description = None
            is_auto_generated = False
            scanner_name = None
            watchlist_mode = "static"
            source_scan_date = None
            created_at = datetime.now()
            updated_at = datetime.now()
            symbols = []

        data = {
            "total": 2,
            "items": [MockWatchlist(), MockWatchlist()],
        }
        response = WatchlistListResponse(**data)
        assert response.total == 2
        assert len(response.items) == 2


class TestCategoryWatchlistsSchema:
    """Test CategoryWatchlists schema validation."""

    def test_category_watchlists(self):
        """Test CategoryWatchlists groups watchlists by category."""
        from src.api.watchlists.schemas import CategoryWatchlists

        class MockCategory:
            id = 1
            name = "Test Category"
            description = "Test"
            color = "#FFF"
            icon = "test"
            created_at = datetime.now()
            updated_at = datetime.now()

        class MockWatchlist:
            id = 1
            name = "Watchlist 1"
            category_id = 1
            description = None
            is_auto_generated = False
            scanner_name = None
            watchlist_mode = "static"
            source_scan_date = None
            created_at = datetime.now()
            updated_at = datetime.now()
            symbols = []

        data = {
            "category": MockCategory(),
            "watchlists": [MockWatchlist()],
        }
        response = CategoryWatchlists(**data)
        assert response.category.id == 1
        assert len(response.watchlists) == 1


class TestWatchlistCloneRequestSchema:
    """Test WatchlistCloneRequest schema validation."""

    def test_watchlist_clone_request_required_fields(self):
        """Test WatchlistCloneRequest with required fields."""
        from src.api.watchlists.schemas import WatchlistCloneRequest

        data = {"name": "Cloned Watchlist"}
        clone_req = WatchlistCloneRequest(**data)
        assert clone_req.name == "Cloned Watchlist"
        assert clone_req.category_id is None
        assert clone_req.description is None

    def test_watchlist_clone_request_with_optional_fields(self):
        """Test WatchlistCloneRequest with optional fields."""
        from src.api.watchlists.schemas import WatchlistCloneRequest

        data = {
            "name": "Cloned Watchlist",
            "category_id": 3,
            "description": "Copy of original",
        }
        clone_req = WatchlistCloneRequest(**data)
        assert clone_req.name == "Cloned Watchlist"
        assert clone_req.category_id == 3
        assert clone_req.description == "Copy of original"
