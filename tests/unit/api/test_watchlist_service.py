"""Unit tests for WatchlistService."""

import pytest
from sqlalchemy.orm import Session

from src.api.watchlists.service import WatchlistService
from src.db.models import Stock, User, Watchlist, WatchlistSymbol


class TestCreateWatchlist:
    """Test create_watchlist method."""

    def test_create_watchlist(self, db_session: Session):
        """Test creating a watchlist with correct fields."""
        # Create a user
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        # Create watchlist
        service = WatchlistService(db_session)
        watchlist = service.create_watchlist(
            user_id=user.id,
            name="My Watchlist",
            description="Test description",
            category_id=None,
        )

        # Verify watchlist was created correctly
        assert watchlist is not None
        assert watchlist.id is not None
        assert watchlist.name == "My Watchlist"
        assert watchlist.description == "Test description"
        assert watchlist.user_id == user.id
        assert watchlist.category_id is None
        assert watchlist.is_auto_generated is False
        assert watchlist.watchlist_mode == "static"
        assert watchlist.created_at is not None
        assert watchlist.updated_at is not None

    def test_create_watchlist_with_category(self, db_session: Session):
        """Test creating a watchlist with a category."""
        from src.db.models import WatchlistCategory

        # Create user and category
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        category = WatchlistCategory(
            user_id=user.id,
            name="Tech Stocks",
            description="Technology companies",
        )
        db_session.add(category)
        db_session.commit()

        # Create watchlist with category
        service = WatchlistService(db_session)
        watchlist = service.create_watchlist(
            user_id=user.id,
            name="Tech Watchlist",
            category_id=category.id,
        )

        # Verify category was set
        assert watchlist.category_id == category.id
        assert watchlist.name == "Tech Watchlist"


class TestGetUserWatchlists:
    """Test get_user_watchlists method."""

    def test_get_user_watchlists(self, db_session: Session):
        """Test retrieving all user's watchlists ordered by created_at desc."""
        # Create user
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        # Create multiple watchlists
        service = WatchlistService(db_session)
        watchlist1 = service.create_watchlist(user_id=user.id, name="First Watchlist")
        watchlist2 = service.create_watchlist(user_id=user.id, name="Second Watchlist")
        watchlist3 = service.create_watchlist(user_id=user.id, name="Third Watchlist")

        # Get all user watchlists
        watchlists = service.get_user_watchlists(user_id=user.id)

        # Verify ordering (most recent first)
        assert len(watchlists) == 3
        assert watchlists[0].id == watchlist3.id
        assert watchlists[1].id == watchlist2.id
        assert watchlists[2].id == watchlist1.id

    def test_get_user_watchlists_empty(self, db_session: Session):
        """Test getting watchlists for user with no watchlists."""
        # Create user
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        # Get watchlists
        service = WatchlistService(db_session)
        watchlists = service.get_user_watchlists(user_id=user.id)

        # Verify empty list
        assert watchlists == []


class TestGetWatchlist:
    """Test get_watchlist method."""

    def test_get_watchlist(self, db_session: Session):
        """Test retrieving a watchlist by ID if owned by user."""
        # Create user and watchlist
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        service = WatchlistService(db_session)
        created = service.create_watchlist(user_id=user.id, name="My Watchlist")

        # Get the watchlist
        watchlist = service.get_watchlist(watchlist_id=created.id, user_id=user.id)

        # Verify watchlist was retrieved
        assert watchlist is not None
        assert watchlist.id == created.id
        assert watchlist.name == "My Watchlist"
        assert watchlist.user_id == user.id

    def test_get_watchlist_not_found(self, db_session: Session):
        """Test getting a watchlist that doesn't exist or not owned."""
        # Create user
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        service = WatchlistService(db_session)

        # Test non-existent watchlist
        watchlist = service.get_watchlist(watchlist_id=999, user_id=user.id)
        assert watchlist is None

        # Test watchlist owned by different user
        other_user = User(username="otheruser", password_hash="hash")
        db_session.add(other_user)
        db_session.commit()

        other_watchlist = service.create_watchlist(
            user_id=other_user.id, name="Other Watchlist"
        )

        # Try to get other user's watchlist
        watchlist = service.get_watchlist(
            watchlist_id=other_watchlist.id, user_id=user.id
        )
        assert watchlist is None


class TestUpdateWatchlist:
    """Test update_watchlist method."""

    def test_update_watchlist(self, db_session: Session):
        """Test updating allowed fields of a watchlist."""
        # Create user and watchlist
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        service = WatchlistService(db_session)
        watchlist = service.create_watchlist(
            user_id=user.id,
            name="Original Name",
            description="Original description",
        )

        # Update watchlist
        updated = service.update_watchlist(
            watchlist_id=watchlist.id,
            user_id=user.id,
            name="Updated Name",
            description="Updated description",
        )

        # Verify updates
        assert updated is not None
        assert updated.id == watchlist.id
        assert updated.name == "Updated Name"
        assert updated.description == "Updated description"

    def test_update_watchlist_partial(self, db_session: Session):
        """Test partial update of watchlist fields."""
        # Create user and watchlist
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        service = WatchlistService(db_session)
        watchlist = service.create_watchlist(
            user_id=user.id,
            name="Original Name",
            description="Original description",
        )

        # Update only name
        updated = service.update_watchlist(
            watchlist_id=watchlist.id,
            user_id=user.id,
            name="New Name",
        )

        # Verify only name changed
        assert updated.name == "New Name"
        assert updated.description == "Original description"

    def test_update_watchlist_not_found(self, db_session: Session):
        """Test updating a watchlist that doesn't exist or not owned."""
        # Create user
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        service = WatchlistService(db_session)

        # Test non-existent watchlist
        result = service.update_watchlist(
            watchlist_id=999,
            user_id=user.id,
            name="Updated",
        )
        assert result is None

        # Test watchlist owned by different user
        other_user = User(username="otheruser", password_hash="hash")
        db_session.add(other_user)
        db_session.commit()

        other_watchlist = service.create_watchlist(
            user_id=other_user.id, name="Other Watchlist"
        )

        # Try to update other user's watchlist
        result = service.update_watchlist(
            watchlist_id=other_watchlist.id,
            user_id=user.id,
            name="Hacked",
        )
        assert result is None


class TestDeleteWatchlist:
    """Test delete_watchlist method."""

    def test_delete_watchlist(self, db_session: Session):
        """Test deleting a watchlist if owned by user."""
        # Create user and watchlist
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        service = WatchlistService(db_session)
        watchlist = service.create_watchlist(user_id=user.id, name="To Delete")

        # Delete the watchlist
        result = service.delete_watchlist(watchlist_id=watchlist.id, user_id=user.id)

        # Verify deletion
        assert result is True

        # Verify it's actually deleted
        deleted = (
            db_session.query(Watchlist)
            .filter(Watchlist.id == watchlist.id)
            .first()
        )
        assert deleted is None

    def test_delete_watchlist_not_found(self, db_session: Session):
        """Test deleting a watchlist that doesn't exist or not owned."""
        # Create user
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        service = WatchlistService(db_session)

        # Test non-existent watchlist
        result = service.delete_watchlist(watchlist_id=999, user_id=user.id)
        assert result is False

        # Test watchlist owned by different user
        other_user = User(username="otheruser", password_hash="hash")
        db_session.add(other_user)
        db_session.commit()

        other_watchlist = service.create_watchlist(
            user_id=other_user.id, name="Other Watchlist"
        )

        # Try to delete other user's watchlist
        result = service.delete_watchlist(
            watchlist_id=other_watchlist.id, user_id=user.id
        )
        assert result is False

        # Verify other user's watchlist still exists
        still_exists = (
            db_session.query(Watchlist)
            .filter(Watchlist.id == other_watchlist.id)
            .first()
        )
        assert still_exists is not None

    def test_delete_watchlist_with_symbols(self, db_session: Session):
        """Test that deleting a watchlist cascades to its symbols."""
        from src.db.models import WatchlistSymbol, Stock

        # Create user, stock, and watchlist with symbols
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        stock = Stock(symbol="AAPL", name="Apple Inc.")
        db_session.add(stock)
        db_session.commit()

        service = WatchlistService(db_session)
        watchlist = service.create_watchlist(user_id=user.id, name="To Delete")

        # Add symbol to watchlist
        symbol = WatchlistSymbol(
            watchlist_id=watchlist.id,
            stock_id=stock.id,
            notes="Test note",
        )
        db_session.add(symbol)
        db_session.commit()

        # Delete the watchlist
        result = service.delete_watchlist(watchlist_id=watchlist.id, user_id=user.id)

        # Verify deletion succeeded
        assert result is True

        # Verify symbols were cascade deleted
        symbols = (
            db_session.query(WatchlistSymbol)
            .filter(WatchlistSymbol.watchlist_id == watchlist.id)
            .all()
        )
        assert len(symbols) == 0


class TestAddSymbol:
    """Test add_symbol method."""

    def test_add_symbol(self, db_session: Session):
        """Test adding a symbol to a watchlist."""
        # Create user and watchlist
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        stock = Stock(symbol="AAPL", name="Apple Inc.")
        db_session.add(stock)
        db_session.commit()

        service = WatchlistService(db_session)
        watchlist = service.create_watchlist(user_id=user.id, name="Tech Stocks")

        # Add symbol
        symbol = service.add_symbol(
            watchlist_id=watchlist.id,
            user_id=user.id,
            symbol="AAPL",
            notes="Great company",
        )

        # Verify symbol was added
        assert symbol is not None
        assert symbol.id is not None
        assert symbol.watchlist_id == watchlist.id
        assert symbol.stock_id == stock.id
        assert symbol.notes == "Great company"
        assert symbol.added_at is not None

    def test_add_symbol_duplicate_prevention(self, db_session: Session):
        """Test that duplicate symbols cannot be added to the same watchlist."""
        # Create user and watchlist
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        stock = Stock(symbol="AAPL", name="Apple Inc.")
        db_session.add(stock)
        db_session.commit()

        service = WatchlistService(db_session)
        watchlist = service.create_watchlist(user_id=user.id, name="Tech Stocks")

        # Add symbol first time
        symbol1 = service.add_symbol(
            watchlist_id=watchlist.id,
            user_id=user.id,
            symbol="AAPL",
        )
        assert symbol1 is not None

        # Try to add same symbol again - should fail
        symbol2 = service.add_symbol(
            watchlist_id=watchlist.id,
            user_id=user.id,
            symbol="AAPL",
        )
        assert symbol2 is None

    def test_add_symbol_stock_not_found(self, db_session: Session):
        """Test adding a symbol that doesn't exist in stocks table."""
        # Create user and watchlist
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        service = WatchlistService(db_session)
        watchlist = service.create_watchlist(user_id=user.id, name="Tech Stocks")

        # Try to add non-existent symbol
        symbol = service.add_symbol(
            watchlist_id=watchlist.id,
            user_id=user.id,
            symbol="INVALID",
        )
        assert symbol is None

    def test_add_symbol_watchlist_not_found(self, db_session: Session):
        """Test adding a symbol to a watchlist that doesn't exist or not owned."""
        # Create user
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        stock = Stock(symbol="AAPL", name="Apple Inc.")
        db_session.add(stock)
        db_session.commit()

        service = WatchlistService(db_session)

        # Test non-existent watchlist
        symbol = service.add_symbol(
            watchlist_id=999,
            user_id=user.id,
            symbol="AAPL",
        )
        assert symbol is None

        # Test watchlist owned by different user
        other_user = User(username="otheruser", password_hash="hash")
        db_session.add(other_user)
        db_session.commit()

        other_watchlist = service.create_watchlist(
            user_id=other_user.id, name="Other Watchlist"
        )

        # Try to add to other user's watchlist
        symbol = service.add_symbol(
            watchlist_id=other_watchlist.id,
            user_id=user.id,
            symbol="AAPL",
        )
        assert symbol is None


class TestRemoveSymbol:
    """Test remove_symbol method."""

    def test_remove_symbol(self, db_session: Session):
        """Test removing a symbol from a watchlist."""
        # Create user, stock, and watchlist with symbol
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        stock = Stock(symbol="AAPL", name="Apple Inc.")
        db_session.add(stock)
        db_session.commit()

        service = WatchlistService(db_session)
        watchlist = service.create_watchlist(user_id=user.id, name="Tech Stocks")

        symbol = WatchlistSymbol(
            watchlist_id=watchlist.id,
            stock_id=stock.id,
            notes="To be removed",
        )
        db_session.add(symbol)
        db_session.commit()

        # Remove the symbol
        result = service.remove_symbol(
            watchlist_id=watchlist.id,
            user_id=user.id,
            symbol="AAPL",
        )

        # Verify removal
        assert result is True

        # Verify it's actually deleted
        deleted = (
            db_session.query(WatchlistSymbol)
            .filter(
                WatchlistSymbol.watchlist_id == watchlist.id,
                WatchlistSymbol.stock_id == stock.id,
            )
            .first()
        )
        assert deleted is None

    def test_remove_symbol_not_found(self, db_session: Session):
        """Test removing a symbol that doesn't exist in the watchlist."""
        # Create user and watchlist
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        stock = Stock(symbol="AAPL", name="Apple Inc.")
        db_session.add(stock)
        db_session.commit()

        service = WatchlistService(db_session)
        watchlist = service.create_watchlist(user_id=user.id, name="Tech Stocks")

        # Try to remove symbol that was never added
        result = service.remove_symbol(
            watchlist_id=watchlist.id,
            user_id=user.id,
            symbol="AAPL",
        )
        assert result is False

    def test_remove_symbol_watchlist_not_found(self, db_session: Session):
        """Test removing a symbol from a watchlist that doesn't exist or not owned."""
        # Create user and stock
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        stock = Stock(symbol="AAPL", name="Apple Inc.")
        db_session.add(stock)
        db_session.commit()

        service = WatchlistService(db_session)

        # Test non-existent watchlist
        result = service.remove_symbol(
            watchlist_id=999,
            user_id=user.id,
            symbol="AAPL",
        )
        assert result is False

        # Test watchlist owned by different user
        other_user = User(username="otheruser", password_hash="hash")
        db_session.add(other_user)
        db_session.commit()

        other_watchlist = service.create_watchlist(
            user_id=other_user.id, name="Other Watchlist"
        )

        # Try to remove from other user's watchlist
        result = service.remove_symbol(
            watchlist_id=other_watchlist.id,
            user_id=user.id,
            symbol="AAPL",
        )
        assert result is False


class TestGetWatchlistSymbols:
    """Test get_watchlist_symbols method."""

    def test_get_watchlist_symbols(self, db_session: Session):
        """Test retrieving all symbols from a watchlist."""
        # Create user, stocks, and watchlist with multiple symbols
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        stock1 = Stock(symbol="AAPL", name="Apple Inc.")
        stock2 = Stock(symbol="MSFT", name="Microsoft Corp.")
        stock3 = Stock(symbol="GOOGL", name="Alphabet Inc.")
        db_session.add_all([stock1, stock2, stock3])
        db_session.commit()

        service = WatchlistService(db_session)
        watchlist = service.create_watchlist(user_id=user.id, name="Tech Stocks")

        # Add symbols
        symbol1 = WatchlistSymbol(
            watchlist_id=watchlist.id,
            stock_id=stock1.id,
            notes="Apple",
            priority=1,
        )
        symbol2 = WatchlistSymbol(
            watchlist_id=watchlist.id,
            stock_id=stock2.id,
            notes="Microsoft",
            priority=2,
        )
        symbol3 = WatchlistSymbol(
            watchlist_id=watchlist.id,
            stock_id=stock3.id,
            notes="Google",
            priority=3,
        )
        db_session.add_all([symbol1, symbol2, symbol3])
        db_session.commit()

        # Get symbols
        symbols = service.get_watchlist_symbols(
            watchlist_id=watchlist.id,
            user_id=user.id,
        )

        # Verify symbols retrieved with stock info
        assert len(symbols) == 3
        assert symbols[0].stock.symbol == "AAPL"
        assert symbols[0].notes == "Apple"
        assert symbols[1].stock.symbol == "MSFT"
        assert symbols[2].stock.symbol == "GOOGL"

    def test_get_watchlist_symbols_empty(self, db_session: Session):
        """Test retrieving symbols from an empty watchlist."""
        # Create user and watchlist
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        service = WatchlistService(db_session)
        watchlist = service.create_watchlist(user_id=user.id, name="Empty Watchlist")

        # Get symbols
        symbols = service.get_watchlist_symbols(
            watchlist_id=watchlist.id,
            user_id=user.id,
        )

        # Verify empty list
        assert symbols == []

    def test_get_watchlist_symbols_not_found(self, db_session: Session):
        """Test retrieving symbols from a watchlist that doesn't exist or not owned."""
        # Create user
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        service = WatchlistService(db_session)

        # Test non-existent watchlist
        symbols = service.get_watchlist_symbols(
            watchlist_id=999,
            user_id=user.id,
        )
        assert symbols == []

        # Test watchlist owned by different user
        other_user = User(username="otheruser", password_hash="hash")
        db_session.add(other_user)
        db_session.commit()

        other_watchlist = service.create_watchlist(
            user_id=other_user.id, name="Other Watchlist"
        )

        # Try to get other user's watchlist symbols
        symbols = service.get_watchlist_symbols(
            watchlist_id=other_watchlist.id,
            user_id=user.id,
        )
        assert symbols == []


class TestCreateCategory:
    """Test create_category method."""

    def test_create_category(self, db_session: Session):
        """Test creating a category with correct fields."""
        from src.db.models import WatchlistCategory

        # Create a user
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        # Create category
        service = WatchlistService(db_session)
        category = service.create_category(
            user_id=user.id,
            name="Tech Stocks",
            icon="💻",
            is_system=False,
        )

        # Verify category was created correctly
        assert category is not None
        assert category.id is not None
        assert category.name == "Tech Stocks"
        assert category.icon == "💻"
        assert category.user_id == user.id
        assert category.is_system is False
        assert category.sort_order == 0
        assert category.created_at is not None
        assert category.updated_at is not None

    def test_create_category_with_optional_fields(self, db_session: Session):
        """Test creating a category with description and color."""
        from src.db.models import WatchlistCategory

        # Create a user
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        # Create category with optional fields
        service = WatchlistService(db_session)
        category = service.create_category(
            user_id=user.id,
            name="Momentum Plays",
            icon="🚀",
            description="High momentum stocks",
            color="#FF5733",
        )

        # Verify optional fields
        assert category.name == "Momentum Plays"
        assert category.icon == "🚀"
        assert category.description == "High momentum stocks"
        assert category.color == "#FF5733"


class TestGetOrCreateDefaultCategories:
    """Test get_or_create_default_categories method."""

    def test_creates_default_categories(self, db_session: Session):
        """Test that default categories are created with correct properties."""
        from src.db.models import WatchlistCategory

        # Create a user
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        # Get or create default categories
        service = WatchlistService(db_session)
        categories = service.get_or_create_default_categories(user_id=user.id)

        # Verify 4 categories were created
        assert len(categories) == 4

        # Verify each category has correct properties
        category_map = {cat.name: cat for cat in categories}

        # Active Trading
        active_trading = category_map["Active Trading"]
        assert active_trading.icon == "🔥"
        assert active_trading.is_system is True
        assert active_trading.sort_order == 1

        # Scanner Results
        scanner_results = category_map["Scanner Results"]
        assert scanner_results.icon == "📊"
        assert scanner_results.is_system is True
        assert scanner_results.sort_order == 2

        # Research
        research = category_map["Research"]
        assert research.icon == "🔬"
        assert research.is_system is True
        assert research.sort_order == 3

        # Archived
        archived = category_map["Archived"]
        assert archived.icon == "📦"
        assert archived.is_system is True
        assert archived.sort_order == 4

    def test_returns_existing_categories(self, db_session: Session):
        """Test that existing categories are returned without duplicates."""
        from src.db.models import WatchlistCategory

        # Create a user
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        # Create default categories once
        service = WatchlistService(db_session)
        categories1 = service.get_or_create_default_categories(user_id=user.id)

        # Call again - should return same categories
        categories2 = service.get_or_create_default_categories(user_id=user.id)

        # Verify same categories returned
        assert len(categories1) == len(categories2) == 4
        cat1_ids = {cat.id for cat in categories1}
        cat2_ids = {cat.id for cat in categories2}
        assert cat1_ids == cat2_ids

        # Verify no duplicates were created
        all_categories = (
            db_session.query(WatchlistCategory)
            .filter(WatchlistCategory.user_id == user.id)
            .all()
        )
        assert len(all_categories) == 4


class TestGetUserCategories:
    """Test get_user_categories method."""

    def test_get_user_categories_ordered(self, db_session: Session):
        """Test retrieving categories ordered by sort_order."""
        from src.db.models import WatchlistCategory

        # Create a user
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        # Create categories with different sort_order values
        service = WatchlistService(db_session)
        cat1 = service.create_category(user_id=user.id, name="Category 1", icon="1️⃣")
        cat1.sort_order = 3
        db_session.commit()

        cat2 = service.create_category(user_id=user.id, name="Category 2", icon="2️⃣")
        cat2.sort_order = 1
        db_session.commit()

        cat3 = service.create_category(user_id=user.id, name="Category 3", icon="3️⃣")
        cat3.sort_order = 2
        db_session.commit()

        # Get categories
        categories = service.get_user_categories(user_id=user.id)

        # Verify ordering by sort_order
        assert len(categories) == 3
        assert categories[0].name == "Category 2"
        assert categories[1].name == "Category 3"
        assert categories[2].name == "Category 1"

    def test_get_user_categories_empty(self, db_session: Session):
        """Test getting categories for user with no categories."""
        # Create a user
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        # Get categories
        service = WatchlistService(db_session)
        categories = service.get_user_categories(user_id=user.id)

        # Verify empty list
        assert categories == []

    def test_get_user_categories_includes_defaults(self, db_session: Session):
        """Test that default categories are included."""
        # Create a user
        user = User(username="testuser", password_hash="hash")
        db_session.add(user)
        db_session.commit()

        # Create default categories
        service = WatchlistService(db_session)
        service.get_or_create_default_categories(user_id=user.id)

        # Add a custom category
        custom = service.create_category(user_id=user.id, name="Custom", icon="⭐")
        custom.sort_order = 5
        db_session.commit()

        # Get all categories
        categories = service.get_user_categories(user_id=user.id)

        # Verify all categories returned in correct order
        assert len(categories) == 5
        assert categories[0].name == "Active Trading"
        assert categories[1].name == "Scanner Results"
        assert categories[2].name == "Research"
        assert categories[3].name == "Archived"
        assert categories[4].name == "Custom"
