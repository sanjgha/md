"""Unit tests for WatchlistService."""

import pytest
from sqlalchemy.orm import Session

from src.api.watchlists.service import WatchlistService
from src.db.models import User, Watchlist


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
