"""Tests for watchlist database models."""

import pytest
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from src.db.models import Watchlist, WatchlistSymbol, WatchlistCategory, User, Stock


def test_watchlist_creation(db_session):
    """Verify Watchlist model can be created with basic fields."""
    # Create a user first
    user = User(username="testuser", password_hash="hash123")
    db_session.add(user)
    db_session.flush()

    # Create watchlist
    watchlist = Watchlist(
        user_id=user.id,
        name="My Watchlist",
        description="Test watchlist description",
        is_auto_generated=False,
    )
    db_session.add(watchlist)
    db_session.commit()

    # Retrieve and verify
    retrieved = db_session.query(Watchlist).filter_by(name="My Watchlist").first()
    assert retrieved is not None
    assert retrieved.user_id == user.id
    assert retrieved.name == "My Watchlist"
    assert retrieved.description == "Test watchlist description"
    assert retrieved.is_auto_generated is False
    assert retrieved.created_at is not None


def test_watchlist_with_symbols(db_session):
    """Verify Watchlist can have multiple WatchlistSymbol entries."""
    # Create user and watchlist
    user = User(username="testuser2", password_hash="hash123")
    db_session.add(user)
    db_session.flush()

    watchlist = Watchlist(
        user_id=user.id,
        name="Tech Stocks",
        description="Technology stocks watchlist",
    )
    db_session.add(watchlist)
    db_session.flush()

    # Create stocks
    stock1 = Stock(symbol="AAPL", name="Apple Inc.", sector="Technology")
    stock2 = Stock(symbol="MSFT", name="Microsoft", sector="Technology")
    db_session.add_all([stock1, stock2])
    db_session.flush()

    # Add symbols to watchlist
    symbol1 = WatchlistSymbol(
        watchlist_id=watchlist.id,
        stock_id=stock1.id,
        notes="Good momentum",
    )
    symbol2 = WatchlistSymbol(
        watchlist_id=watchlist.id,
        stock_id=stock2.id,
        notes="Strong earnings",
    )
    db_session.add_all([symbol1, symbol2])
    db_session.commit()

    # Retrieve and verify
    retrieved = db_session.query(Watchlist).filter_by(name="Tech Stocks").first()
    assert len(retrieved.symbols) == 2
    assert retrieved.symbols[0].notes == "Good momentum"
    assert retrieved.symbols[1].notes == "Strong earnings"


def test_watchlist_category_creation(db_session):
    """Verify WatchlistCategory model can be created."""
    user = User(username="testuser3", password_hash="hash123")
    db_session.add(user)
    db_session.flush()

    category = WatchlistCategory(
        user_id=user.id,
        name="Momentum",
        description="Momentum-based watchlists",
        color="#FF5733",
    )
    db_session.add(category)
    db_session.commit()

    # Retrieve and verify
    retrieved = db_session.query(WatchlistCategory).filter_by(name="Momentum").first()
    assert retrieved is not None
    assert retrieved.user_id == user.id
    assert retrieved.name == "Momentum"
    assert retrieved.description == "Momentum-based watchlists"
    assert retrieved.color == "#FF5733"


def test_watchlist_with_category(db_session):
    """Verify Watchlist can belong to a WatchlistCategory."""
    user = User(username="testuser4", password_hash="hash123")
    db_session.add(user)
    db_session.flush()

    # Create category
    category = WatchlistCategory(
        user_id=user.id,
        name="Swing Trading",
        description="Swing trading setups",
    )
    db_session.add(category)
    db_session.flush()

    # Create watchlist with category
    watchlist = Watchlist(
        user_id=user.id,
        name="Swing Candidates",
        category_id=category.id,
        description="Potential swing trades",
    )
    db_session.add(watchlist)
    db_session.commit()

    # Retrieve and verify
    retrieved = db_session.query(Watchlist).filter_by(name="Swing Candidates").first()
    assert retrieved.category_id == category.id
    assert retrieved.category.name == "Swing Trading"


def test_user_watchlist_relationships(db_session):
    """Verify User model has watchlists and watchlist_categories relationships."""
    user = User(username="testuser5", password_hash="hash123")
    db_session.add(user)
    db_session.flush()

    # Create watchlists
    watchlist1 = Watchlist(user_id=user.id, name="Watchlist 1")
    watchlist2 = Watchlist(user_id=user.id, name="Watchlist 2")
    db_session.add_all([watchlist1, watchlist2])
    db_session.flush()

    # Create categories
    category1 = WatchlistCategory(user_id=user.id, name="Category 1")
    category2 = WatchlistCategory(user_id=user.id, name="Category 2")
    db_session.add_all([category1, category2])
    db_session.commit()

    # Retrieve and verify relationships
    retrieved = db_session.query(User).filter_by(username="testuser5").first()
    assert len(retrieved.watchlists) == 2
    assert len(retrieved.watchlist_categories) == 2
    assert retrieved.watchlists[0].name == "Watchlist 1"
    assert retrieved.watchlist_categories[0].name == "Category 1"


def test_watchlist_symbol_unique_constraint(db_session):
    """Verify WatchlistSymbol has unique constraint on (watchlist_id, stock_id)."""
    user = User(username="testuser6", password_hash="hash123")
    db_session.add(user)
    db_session.flush()

    watchlist = Watchlist(user_id=user.id, name="Unique Test")
    db_session.add(watchlist)
    db_session.flush()

    stock = Stock(symbol="AAPL", name="Apple")
    db_session.add(stock)
    db_session.flush()

    # Add same stock twice - should violate unique constraint
    symbol1 = WatchlistSymbol(watchlist_id=watchlist.id, stock_id=stock.id)
    symbol2 = WatchlistSymbol(watchlist_id=watchlist.id, stock_id=stock.id)
    db_session.add(symbol1)
    db_session.add(symbol2)

    # This should raise an integrity error
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_watchlist_tablename():
    """Verify Watchlist table name."""
    assert Watchlist.__tablename__ == "watchlists"


def test_watchlist_symbol_tablename():
    """Verify WatchlistSymbol table name."""
    assert WatchlistSymbol.__tablename__ == "watchlist_symbols"


def test_watchlist_category_tablename():
    """Verify WatchlistCategory table name."""
    assert WatchlistCategory.__tablename__ == "watchlist_categories"


def test_watchlist_symbol_has_watchlist_id_fk():
    """Verify WatchlistSymbol has foreign key to Watchlist."""
    col = WatchlistSymbol.__table__.c["watchlist_id"]
    assert col.nullable is False
    assert len(col.foreign_keys) == 1


def test_watchlist_symbol_has_stock_id_fk():
    """Verify WatchlistSymbol has foreign key to Stock."""
    col = WatchlistSymbol.__table__.c["stock_id"]
    assert col.nullable is False
    assert len(col.foreign_keys) == 1


def test_watchlist_has_category_id_fk():
    """Verify Watchlist has optional foreign key to WatchlistCategory."""
    col = Watchlist.__table__.c["category_id"]
    assert col.nullable is True
    assert len(col.foreign_keys) == 1


def test_watchlist_symbol_unique_constraint_exists():
    """Verify WatchlistSymbol has unique constraint on (watchlist_id, stock_id)."""
    constraint_names = {c.name for c in WatchlistSymbol.__table__.constraints}
    assert "uq_watchlist_symbols_watchlist_stock" in constraint_names
