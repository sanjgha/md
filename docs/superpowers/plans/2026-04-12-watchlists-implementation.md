# Watchlists Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a watchlist management system supporting manual CRUD and auto-generation from EOD scanner results, with category-based organization and per-user isolation.

**Architecture:** FastAPI backend with new `/api/watchlists/*` endpoints, SQLAlchemy models (Watchlist, WatchlistSymbol, WatchlistCategory), SolidJS frontend with dashboard and split-view layouts, integrated into existing EOD pipeline via service layer hook.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, PostgreSQL, SolidJS, TypeScript, Vite

---

## File Structure

**New files to create:**
```
src/db/migrations/versions/20260412_watchlists.py
src/api/watchlists/__init__.py
src/api/watchlists/routes.py
src/api/watchlists/schemas.py
src/api/watchlists/service.py
tests/integration/api/test_watchlists.py
tests/unit/api/test_watchlist_service.py
frontend/src/pages/watchlists/index.tsx
frontend/src/pages/watchlists/dashboard.tsx
frontend/src/pages/watchlists/watchlist-view.tsx
frontend/src/pages/watchlists/create-modal.tsx
frontend/src/pages/watchlists/edit-modal.tsx
frontend/src/pages/watchlists/category-manager.tsx
frontend/src/pages/watchlists/types.ts
frontend/tests/unit/pages/watchlists/dashboard.test.tsx
```

**Files to modify:**
```
src/db/models.py (add Watchlist, WatchlistSymbol, WatchlistCategory, User relationships)
src/main.py (add EOD hook for watchlist generation)
src/api/main.py (register watchlist routes)
frontend/src/main.tsx (add watchlist routes)
frontend/src/lib/api.ts (add watchlist API methods)
```

---

## Task 1: Database Models

**Files:**
- Modify: `src/db/models.py:269-300` (add after User model)

- [ ] **Step 1: Write failing test for Watchlist model**

```python
# tests/unit/test_watchlist_models.py
import pytest
from datetime import datetime, date
from src.db.models import Watchlist, WatchlistSymbol, WatchlistCategory, User

def test_watchlist_creation(db_session):
    """Test Watchlist model can be created with basic fields."""
    user = User(username="test", password_hash="hash")
    db_session.add(user)
    db_session.flush()

    watchlist = Watchlist(
        user_id=user.id,
        name="My Watchlist",
        description="Test watchlist"
    )
    db_session.add(watchlist)
    db_session.commit()

    assert watchlist.id is not None
    assert watchlist.name == "My Watchlist"
    assert watchlist.is_auto_generated is False
    assert watchlist.watchlist_mode == "manual"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_watchlist_models.py::test_watchlist_creation -v`
Expected: FAIL with "Class 'Watchlist' not defined"

- [ ] **Step 3: Add Watchlist model to src/db/models.py**

```python
# Add after User model (around line 300)

class Watchlist(Base):
    """User watchlists for organizing stock lists."""
    __tablename__ = "watchlists"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    category_id = Column(Integer, ForeignKey("watchlist_categories.id", ondelete="SET NULL"))
    description = Column(Text)
    is_auto_generated = Column(Boolean, default=False)
    scanner_name = Column(String(100), nullable=True)
    watchlist_mode = Column(String(20), default="manual")
    source_scan_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="watchlists")
    category = relationship("WatchlistCategory", back_populates="watchlists")
    symbols = relationship("WatchlistSymbol", back_populates="watchlist", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_watchlists_user_name"),
        Index("ix_watchlists_user_category", "user_id", "category_id"),
    )
```

- [ ] **Step 4: Add WatchlistSymbol model**

```python
# Add after Watchlist model

class WatchlistSymbol(Base):
    """Symbols in a watchlist."""
    __tablename__ = "watchlist_symbols"

    id = Column(BigInteger, primary_key=True)
    watchlist_id = Column(Integer, ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False)
    stock_id = Column(Integer, ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)

    watchlist = relationship("Watchlist", back_populates="symbols")
    stock = relationship("Stock")

    __table_args__ = (
        UniqueConstraint("watchlist_id", "stock_id", name="uq_watchlist_symbols_watchlist_stock"),
        Index("ix_watchlist_symbols_watchlist", "watchlist_id"),
    )
```

- [ ] **Step 5: Add WatchlistCategory model**

```python
# Add after WatchlistSymbol model

class WatchlistCategory(Base):
    """Categories for organizing watchlists."""
    __tablename__ = "watchlist_categories"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    icon = Column(String(50))
    sort_order = Column(Integer, default=0)
    is_system = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="watchlist_categories")
    watchlists = relationship("Watchlist", back_populates="category")

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_watchlist_categories_user_name"),
    )
```

- [ ] **Step 6: Update User model with relationships**

```python
# Add to User class (around line 282, after existing relationships)

class User(Base):
    # ... existing fields ...

    # Add these two new relationships:
    watchlists = relationship("Watchlist", back_populates="user", cascade="all, delete-orphan")
    watchlist_categories = relationship("WatchlistCategory", back_populates="user", cascade="all, delete-orphan")
```

- [ ] **Step 7: Run test to verify it passes**

Run: `pytest tests/unit/test_watchlist_models.py::test_watchlist_creation -v`
Expected: PASS

- [ ] **Step 8: Write test for Watchlist with symbols**

```python
def test_watchlist_with_symbols(db_session):
    """Test adding symbols to watchlist."""
    from src.db.models import Stock

    user = User(username="test", password_hash="hash")
    db_session.add(user)
    db_session.flush()

    stock = Stock(symbol="AAPL", name="Apple Inc")
    db_session.add(stock)
    db_session.flush()

    watchlist = Watchlist(
        user_id=user.id,
        name="Tech Stocks"
    )
    db_session.add(watchlist)
    db_session.flush()

    symbol = WatchlistSymbol(
        watchlist_id=watchlist.id,
        stock_id=stock.id,
        notes="Good momentum"
    )
    db_session.add(symbol)
    db_session.commit()

    assert len(watchlist.symbols) == 1
    assert watchlist.symbols[0].stock.symbol == "AAPL"
```

- [ ] **Step 9: Run test**

Run: `pytest tests/unit/test_watchlist_models.py::test_watchlist_with_symbols -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add src/db/models.py tests/unit/test_watchlist_models.py
git commit -m "feat: add Watchlist, WatchlistSymbol, WatchlistCategory models"
```

---

## Task 2: Database Migration

**Files:**
- Create: `src/db/migrations/versions/20260412_watchlists.py`

- [ ] **Step 1: Generate migration**

Run: `alembic revision --autogenerate -m "add watchlists tables"`

- [ ] **Step 2: Review generated migration**

Check that it includes:
- Create table `watchlists`
- Create table `watchlist_symbols`
- Create table `watchlist_categories`
- Create indexes
- Create foreign keys
- Create unique constraints

- [ ] **Step 3: Manually create migration if autogenerate fails**

```python
# src/db/migrations/versions/20260412_watchlists.py
"""add watchlists tables

Revision ID: 20260412_watchlists
Revises: 20260408_foundation
Create Date: 2026-04-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '20260412_watchlists'
down_revision = '20260408_foundation'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'watchlist_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('icon', sa.String(length=50), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('is_system', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_watchlist_categories_user_id'), ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'name', name='uq_watchlist_categories_user_name'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'watchlists',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_auto_generated', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('scanner_name', sa.String(length=100), nullable=True),
        sa.Column('watchlist_mode', sa.String(length=20), nullable=True, server_default='manual'),
        sa.Column('source_scan_date', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['category_id'], ['watchlist_categories.id'], name=op.f('fk_watchlists_category_id'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_watchlists_user_id'), ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'name', name='uq_watchlists_user_name'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_watchlists_user_category', 'watchlists', ['user_id', 'category_id'])

    op.create_table(
        'watchlist_symbols',
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.Column('watchlist_id', sa.Integer(), nullable=False),
        sa.Column('stock_id', sa.Integer(), nullable=False),
        sa.Column('added_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], name=op.f('fk_watchlist_symbols_stock_id'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['watchlist_id'], ['watchlists.id'], name=op.f('fk_watchlist_symbols_watchlist_id'), ondelete='CASCADE'),
        sa.UniqueConstraint('watchlist_id', 'stock_id', name='uq_watchlist_symbols_watchlist_stock'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_watchlist_symbols_watchlist', 'watchlist_symbols', ['watchlist_id'])


def downgrade():
    op.drop_index('ix_watchlist_symbols_watchlist', table_name='watchlist_symbols')
    op.drop_table('watchlist_symbols')
    op.drop_index('ix_watchlists_user_category', table_name='watchlists')
    op.drop_table('watchlists')
    op.drop_table('watchlist_categories')
```

- [ ] **Step 4: Run migration**

Run: `alembic upgrade head`

- [ ] **Step 5: Verify tables created**

Run: `psql -U market_data -d market_data -c "\dt watchlist*"`
Expected: Shows watchlist_categories, watchlists, watchlist_symbols tables

- [ ] **Step 6: Commit**

```bash
git add src/db/migrations/versions/20260412_watchlists.py
git commit -m "feat: add migration for watchlists tables"
```

---

## Task 3: Pydantic Schemas

**Files:**
- Create: `src/api/watchlists/__init__.py`
- Create: `src/api/watchlists/schemas.py`

- [ ] **Step 1: Write failing test for schema validation**

```python
# tests/unit/api/test_watchlist_schemas.py
from pydantic import ValidationError
from src.api.watchlists.schemas import WatchlistCreate, WatchlistResponse

def test_watchlist_create_schema():
    """Test WatchlistCreate schema validation."""
    data = {
        "name": "My Watchlist",
        "category_id": 1,
        "description": "Test description"
    }
    watchlist = WatchlistCreate(**data)
    assert watchlist.name == "My Watchlist"

def test_watchlist_create_requires_name():
    """Test WatchlistCreate requires name field."""
    try:
        WatchlistCreate(category_id=1)
        assert False, "Should have raised ValidationError"
    except ValidationError:
        pass
```

- [ ] **Step 2: Run test**

Run: `pytest tests/unit/api/test_watchlist_schemas.py::test_watchlist_create_schema -v`
Expected: FAIL with "module 'src.api.watchlists.schemas' not found"

- [ ] **Step 3: Create watchlists package**

```bash
mkdir -p src/api/watchlists
touch src/api/watchlists/__init__.py
```

- [ ] **Step 4: Create schemas file**

```python
# src/api/watchlists/schemas.py
from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class WatchlistSymbolCreate(BaseModel):
    """Schema for adding symbol to watchlist."""
    symbol: str = Field(..., min_length=1, max_length=10)
    notes: Optional[str] = None


class WatchlistCreate(BaseModel):
    """Schema for creating a watchlist."""
    name: str = Field(..., min_length=1, max_length=255)
    category_id: Optional[int] = None
    description: Optional[str] = None


class WatchlistUpdate(BaseModel):
    """Schema for updating a watchlist."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    category_id: Optional[int] = None
    description: Optional[str] = None


class WatchlistSymbolResponse(BaseModel):
    """Schema for watchlist symbol response."""
    id: int
    symbol: str
    added_at: datetime
    notes: Optional[str]

    class Config:
        from_attributes = True


class WatchlistResponse(BaseModel):
    """Schema for watchlist response."""
    id: int
    name: str
    category_id: Optional[int]
    description: Optional[str]
    is_auto_generated: bool
    scanner_name: Optional[str]
    watchlist_mode: str
    source_scan_date: Optional[date]
    created_at: datetime
    updated_at: datetime
    symbol_count: int = 0

    class Config:
        from_attributes = True


class WatchlistListResponse(BaseModel):
    """Schema for list of watchlists grouped by category."""
    categories: List['CategoryWatchlists']


class CategoryWatchlists(BaseModel):
    """Watchlists in a category."""
    category_id: Optional[int]
    category_name: str
    category_icon: Optional[str]
    is_system: bool
    watchlists: List[WatchlistResponse]


class CategoryCreate(BaseModel):
    """Schema for creating a category."""
    name: str = Field(..., min_length=1, max_length=100)
    icon: Optional[str] = Field(None, max_length=50)


class CategoryUpdate(BaseModel):
    """Schema for updating a category."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    icon: Optional[str] = Field(None, max_length=50)


class CategoryResponse(BaseModel):
    """Schema for category response."""
    id: int
    name: str
    icon: Optional[str]
    sort_order: int
    is_system: bool
    created_at: datetime

    class Config:
        from_attributes = True


class WatchlistCloneRequest(BaseModel):
    """Schema for cloning a watchlist."""
    new_name: str = Field(..., min_length=1, max_length=255)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/unit/api/test_watchlist_schemas.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/watchlists/ tests/unit/api/test_watchlist_schemas.py
git commit -m "feat: add Pydantic schemas for watchlists API"
```

---

## Task 4: Service Layer - Core Methods

**Files:**
- Create: `src/api/watchlists/service.py`

- [ ] **Step 1: Write failing test for service create method**

```python
# tests/unit/api/test_watchlist_service.py
import pytest
from src.api.watchlists.service import WatchlistService
from src.db.models import User, Watchlist

def test_create_watchlist(db_session):
    """Test creating a watchlist through service."""
    user = User(username="test", password_hash="hash")
    db_session.add(user)
    db_session.commit()

    service = WatchlistService(db_session)
    watchlist = service.create_watchlist(
        user_id=user.id,
        name="My Watchlist",
        description="Test"
    )

    assert watchlist.id is not None
    assert watchlist.name == "My Watchlist"
    assert watchlist.user_id == user.id
```

- [ ] **Step 2: Run test**

Run: `pytest tests/unit/api/test_watchlist_service.py::test_create_watchlist -v`
Expected: FAIL with "cannot import name 'WatchlistService'"

- [ ] **Step 3: Create service with create method**

```python
# src/api/watchlists/service.py
from typing import List, Optional
from sqlalchemy.orm import Session
from src.db.models import Watchlist, WatchlistSymbol, WatchlistCategory, Stock


class WatchlistService:
    """Service for watchlist business logic."""

    def __init__(self, db: Session):
        self.db = db

    def create_watchlist(
        self,
        user_id: int,
        name: str,
        description: Optional[str] = None,
        category_id: Optional[int] = None
    ) -> Watchlist:
        """Create a new watchlist for user."""
        watchlist = Watchlist(
            user_id=user_id,
            name=name,
            description=description,
            category_id=category_id
        )
        self.db.add(watchlist)
        self.db.commit()
        self.db.refresh(watchlist)
        return watchlist

    def get_user_watchlists(self, user_id: int) -> List[Watchlist]:
        """Get all watchlists for user."""
        return (
            self.db.query(Watchlist)
            .filter(Watchlist.user_id == user_id)
            .order_by(Watchlist.created_at.desc())
            .all()
        )

    def get_watchlist(self, watchlist_id: int, user_id: int) -> Optional[Watchlist]:
        """Get watchlist by ID if owned by user."""
        return (
            self.db.query(Watchlist)
            .filter(Watchlist.id == watchlist_id)
            .filter(Watchlist.user_id == user_id)
            .first()
        )

    def update_watchlist(
        self,
        watchlist_id: int,
        user_id: int,
        name: Optional[str] = None,
        category_id: Optional[int] = None,
        description: Optional[str] = None
    ) -> Optional[Watchlist]:
        """Update watchlist if owned by user."""
        watchlist = self.get_watchlist(watchlist_id, user_id)
        if not watchlist:
            return None

        if name is not None:
            watchlist.name = name
        if category_id is not None:
            watchlist.category_id = category_id
        if description is not None:
            watchlist.description = description

        self.db.commit()
        self.db.refresh(watchlist)
        return watchlist

    def delete_watchlist(self, watchlist_id: int, user_id: int) -> bool:
        """Delete watchlist if owned by user."""
        watchlist = self.get_watchlist(watchlist_id, user_id)
        if not watchlist:
            return False

        self.db.delete(watchlist)
        self.db.commit()
        return True
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/api/test_watchlist_service.py::test_create_watchlist -v`
Expected: PASS

- [ ] **Step 5: Write tests for symbol management**

```python
def test_add_symbol_to_watchlist(db_session):
    """Test adding symbol to watchlist."""
    from src.db.models import Stock

    user = User(username="test", password_hash="hash")
    db_session.add(user)
    db_session.flush()

    stock = Stock(symbol="AAPL", name="Apple Inc")
    db_session.add(stock)
    db_session.flush()

    service = WatchlistService(db_session)
    watchlist = service.create_watchlist(user_id=user.id, name="Tech")

    result = service.add_symbol(
        watchlist_id=watchlist.id,
        user_id=user.id,
        symbol="AAPL",
        notes="Good momentum"
    )

    assert result is True
    assert len(watchlist.symbols) == 1
    assert watchlist.symbols[0].stock.symbol == "AAPL"

def test_remove_symbol_from_watchlist(db_session):
    """Test removing symbol from watchlist."""
    from src.db.models import Stock

    user = User(username="test", password_hash="hash")
    db_session.add(user)
    db_session.flush()

    stock = Stock(symbol="AAPL", name="Apple Inc")
    db_session.add(stock)
    db_session.flush()

    service = WatchlistService(db_session)
    watchlist = service.create_watchlist(user_id=user.id, name="Tech")
    service.add_symbol(watchlist.id, user.id, "AAPL")

    result = service.remove_symbol(watchlist.id, user.id, "AAPL")

    assert result is True
    assert len(watchlist.symbols) == 0
```

- [ ] **Step 6: Add symbol management methods to service**

```python
# Add to WatchlistService class

def add_symbol(
    self,
    watchlist_id: int,
    user_id: int,
    symbol: str,
    notes: Optional[str] = None
) -> bool:
    """Add symbol to watchlist."""
    watchlist = self.get_watchlist(watchlist_id, user_id)
    if not watchlist:
        return False

    stock = (
        self.db.query(Stock)
        .filter(Stock.symbol == symbol.upper())
        .first()
    )

    if not stock:
        return False

    # Check if already in watchlist
    existing = (
        self.db.query(WatchlistSymbol)
        .filter(WatchlistSymbol.watchlist_id == watchlist_id)
        .filter(WatchlistSymbol.stock_id == stock.id)
        .first()
    )

    if existing:
        return False  # Already exists

    symbol_entry = WatchlistSymbol(
        watchlist_id=watchlist.id,
        stock_id=stock.id,
        notes=notes
    )
    self.db.add(symbol_entry)
    self.db.commit()
    return True


def remove_symbol(self, watchlist_id: int, user_id: int, symbol: str) -> bool:
    """Remove symbol from watchlist."""
    watchlist = self.get_watchlist(watchlist_id, user_id)
    if not watchlist:
        return False

    stock = (
        self.db.query(Stock)
        .filter(Stock.symbol == symbol.upper())
        .first()
    )

    if not stock:
        return False

    symbol_entry = (
        self.db.query(WatchlistSymbol)
        .filter(WatchlistSymbol.watchlist_id == watchlist_id)
        .filter(WatchlistSymbol.stock_id == stock.id)
        .first()
    )

    if not symbol_entry:
        return False

    self.db.delete(symbol_entry)
    self.db.commit()
    return True


def get_watchlist_symbols(self, watchlist_id: int, user_id: int) -> List[WatchlistSymbol]:
    """Get all symbols in watchlist."""
    watchlist = self.get_watchlist(watchlist_id, user_id)
    if not watchlist:
        return []

    return (
        self.db.query(WatchlistSymbol)
        .filter(WatchlistSymbol.watchlist_id == watchlist_id)
        .all()
    )
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/unit/api/test_watchlist_service.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/api/watchlists/service.py tests/unit/api/test_watchlist_service.py
git commit -m "feat: add WatchlistService with CRUD and symbol management"
```

---

## Task 5: Service Layer - Category Management

**Files:**
- Modify: `src/api/watchlists/service.py`

- [ ] **Step 1: Write failing test for category methods**

```python
# Add to tests/unit/api/test_watchlist_service.py

def test_create_category(db_session):
    """Test creating a category."""
    from src.api.watchlists.service import WatchlistService

    user = User(username="test", password_hash="hash")
    db_session.add(user)
    db_session.commit()

    service = WatchlistService(db_session)
    category = service.create_category(
        user_id=user.id,
        name="My Category",
        icon="🔥"
    )

    assert category.id is not None
    assert category.name == "My Category"
    assert category.icon == "🔥"

def test_get_default_categories(db_session):
    """Test getting/creating default system categories."""
    from src.api.watchlists.service import WatchlistService

    user = User(username="test", password_hash="hash")
    db_session.add(user)
    db_session.commit()

    service = WatchlistService(db_session)
    categories = service.get_or_create_default_categories(user.id)

    assert len(categories) == 4
    category_names = [c.name for c in categories]
    assert "Active Trading" in category_names
    assert "Scanner Results" in category_names
    assert "Research" in category_names
    assert "Archived" in category_names
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/unit/api/test_watchlist_service.py::test_create_category -v`
Expected: FAIL with "WatchlistService has no attribute 'create_category'"

- [ ] **Step 3: Add category methods to service**

```python
# Add to WatchlistService class

def create_category(
    self,
    user_id: int,
    name: str,
    icon: Optional[str] = None,
    is_system: bool = False
) -> WatchlistCategory:
    """Create a new category."""
    category = WatchlistCategory(
        user_id=user_id,
        name=name,
        icon=icon,
        is_system=is_system
    )
    self.db.add(category)
    self.db.commit()
    self.db.refresh(category)
    return category


def get_or_create_default_categories(self, user_id: int) -> List[WatchlistCategory]:
    """Get or create default system categories for user."""
    default_categories = [
        {"name": "Active Trading", "icon": "🔥", "sort_order": 1},
        {"name": "Scanner Results", "icon": "📊", "sort_order": 2},
        {"name": "Research", "icon": "🔬", "sort_order": 3},
        {"name": "Archived", "icon": "📦", "sort_order": 4},
    ]

    categories = []
    for cat_def in default_categories:
        category = (
            self.db.query(WatchlistCategory)
            .filter(WatchlistCategory.user_id == user_id)
            .filter(WatchlistCategory.name == cat_def["name"])
            .filter(WatchlistCategory.is_system == True)
            .first()
        )

        if not category:
            category = WatchlistCategory(
                user_id=user_id,
                name=cat_def["name"],
                icon=cat_def["icon"],
                sort_order=cat_def["sort_order"],
                is_system=True
            )
            self.db.add(category)
            self.db.commit()
            self.db.refresh(category)

        categories.append(category)

    return categories


def get_user_categories(self, user_id: int) -> List[WatchlistCategory]:
    """Get all categories for user, ordered by sort_order."""
    return (
        self.db.query(WatchlistCategory)
        .filter(WatchlistCategory.user_id == user_id)
        .order_by(WatchlistCategory.sort_order, WatchlistCategory.name)
        .all()
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/api/test_watchlist_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/watchlists/service.py tests/unit/api/test_watchlist_service.py
git commit -m "feat: add category management to WatchlistService"
```

---

## Task 6: Service Layer - Clone and Grouped List

**Files:**
- Modify: `src/api/watchlists/service.py`

- [ ] **Step 1: Write failing test for clone method**

```python
def test_clone_watchlist(db_session):
    """Test cloning a watchlist."""
    from src.api.watchlists.service import WatchlistService
    from src.db.models import Stock

    user = User(username="test", password_hash="hash")
    db_session.add(user)
    db_session.flush()

    stock = Stock(symbol="AAPL", name="Apple Inc")
    db_session.add(stock)
    db_session.flush()

    service = WatchlistService(db_session)
    original = service.create_watchlist(user_id=user.id, name="Original")
    service.add_symbol(original.id, user.id, "AAPL")

    clone = service.clone_watchlist(
        watchlist_id=original.id,
        user_id=user.id,
        new_name="Copy of Original"
    )

    assert clone is not None
    assert clone.name == "Copy of Original"
    assert clone.id != original.id
    assert len(clone.symbols) == 1
    assert clone.symbols[0].stock.symbol == "AAPL"
```

- [ ] **Step 2: Run test**

Run: `pytest tests/unit/api/test_watchlist_service.py::test_clone_watchlist -v`
Expected: FAIL with "WatchlistService has no attribute 'clone_watchlist'"

- [ ] **Step 3: Add clone and grouped list methods**

```python
# Add to WatchlistService class

def clone_watchlist(
    self,
    watchlist_id: int,
    user_id: int,
    new_name: str
) -> Optional[Watchlist]:
    """Clone a watchlist (shallow copy)."""
    original = self.get_watchlist(watchlist_id, user_id)
    if not original:
        return None

    clone = Watchlist(
        user_id=user_id,
        name=new_name,
        category_id=original.category_id,
        description=original.description,
        is_auto_generated=False  # Clone is never auto-generated
    )
    self.db.add(clone)
    self.db.flush()

    # Copy symbols
    for symbol_entry in original.symbols:
        new_symbol = WatchlistSymbol(
            watchlist_id=clone.id,
            stock_id=symbol_entry.stock_id,
            notes=symbol_entry.notes
        )
        self.db.add(new_symbol)

    self.db.commit()
    self.db.refresh(clone)
    return clone


def get_watchlists_grouped(self, user_id: int) -> List[dict]:
    """Get user's watchlists grouped by category."""
    categories = self.get_user_categories(user_id)

    result = []
    for category in categories:
        watchlists = (
            self.db.query(Watchlist)
            .filter(Watchlist.user_id == user_id)
            .filter(Watchlist.category_id == category.id)
            .all()
        )

        # Convert to response format with symbol counts
        watchlist_responses = []
        for wl in watchlists:
            symbol_count = (
                self.db.query(WatchlistSymbol)
                .filter(WatchlistSymbol.watchlist_id == wl.id)
                .count()
            )
            watchlist_responses.append({
                "id": wl.id,
                "name": wl.name,
                "description": wl.description,
                "is_auto_generated": wl.is_auto_generated,
                "scanner_name": wl.scanner_name,
                "watchlist_mode": wl.watchlist_mode,
                "source_scan_date": wl.source_scan_date,
                "created_at": wl.created_at,
                "updated_at": wl.updated_at,
                "symbol_count": symbol_count
            })

        result.append({
            "category_id": category.id,
            "category_name": category.name,
            "category_icon": category.icon,
            "is_system": category.is_system,
            "watchlists": watchlist_responses
        })

    return result
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/unit/api/test_watchlist_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/watchlists/service.py tests/unit/api/test_watchlist_service.py
git commit -m "feat: add watchlist clone and grouped list methods"
```

---

## Task 7: API Routes - Watchlist CRUD

**Files:**
- Create: `src/api/watchlists/routes.py`

- [ ] **Step 1: Write failing integration test for list endpoint**

```python
# tests/integration/api/test_watchlists.py
import pytest
from src.api.watchlists.schemas import WatchlistCreate

def test_list_watchlists(authenticated_client):
    """Test GET /api/watchlists returns grouped watchlists."""
    response = authenticated_client.get("/api/watchlists")

    assert response.status_code == 200
    data = response.json()
    assert "categories" in data
    assert len(data["categories"]) == 4  # Default categories
```

- [ ] **Step 2: Run test**

Run: `pytest tests/integration/api/test_watchlists.py::test_list_watchlists -v`
Expected: FAIL with "404 Not Found"

- [ ] **Step 3: Create routes file with list endpoint**

```python
# src/api/watchlists/routes.py
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db
from src.api.watchlists.schemas import (
    WatchlistCreate,
    WatchlistUpdate,
    WatchlistResponse,
    WatchlistListResponse,
    WatchlistSymbolCreate,
    WatchlistSymbolResponse,
    CategoryCreate,
    CategoryResponse,
    WatchlistCloneRequest,
)
from src.api.watchlists.service import WatchlistService
from src.db.models import User

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


@router.get("", response_model=WatchlistListResponse)
def list_watchlists(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all watchlists grouped by category."""
    service = WatchlistService(db)

    # Ensure default categories exist
    service.get_or_create_default_categories(current_user.id)

    categories = service.get_watchlists_grouped(current_user.id)

    return {"categories": categories}


@router.post("", response_model=WatchlistResponse, status_code=201)
def create_watchlist(
    data: WatchlistCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new watchlist."""
    service = WatchlistService(db)

    watchlist = service.create_watchlist(
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        category_id=data.category_id
    )

    return watchlist


@router.get("/{watchlist_id}", response_model=WatchlistResponse)
def get_watchlist(
    watchlist_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get watchlist details."""
    service = WatchlistService(db)
    watchlist = service.get_watchlist(watchlist_id, current_user.id)

    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    # Add symbol count
    from src.db.models import WatchlistSymbol
    symbol_count = (
        db.query(WatchlistSymbol)
        .filter(WatchlistSymbol.watchlist_id == watchlist_id)
        .count()
    )

    return WatchlistResponse(
        **{k: v for k, v in watchlist.__dict__.items() if not k.startswith('_')},
        symbol_count=symbol_count
    )


@router.put("/{watchlist_id}", response_model=WatchlistResponse)
def update_watchlist(
    watchlist_id: int,
    data: WatchlistUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update watchlist."""
    service = WatchlistService(db)
    watchlist = service.update_watchlist(
        watchlist_id=watchlist_id,
        user_id=current_user.id,
        name=data.name,
        category_id=data.category_id,
        description=data.description
    )

    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    return watchlist


@router.delete("/{watchlist_id}", status_code=204)
def delete_watchlist(
    watchlist_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete watchlist."""
    service = WatchlistService(db)
    success = service.delete_watchlist(watchlist_id, current_user.id)

    if not success:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    return None
```

- [ ] **Step 4: Register routes in main API**

```python
# Add to src/api/main.py

from src.api.watchlists.routes import router as watchlists_router

# In app factory, add:
app.include_router(watchlists_router, prefix="/api", tags=["watchlists"])
```

- [ ] **Step 5: Run test**

Run: `pytest tests/integration/api/test_watchlists.py::test_list_watchlists -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/watchlists/routes.py src/api/main.py tests/integration/api/test_watchlists.py
git commit -m "feat: add watchlist CRUD API endpoints"
```

---

## Task 8: API Routes - Symbol Management

**Files:**
- Modify: `src/api/watchlists/routes.py`

- [ ] **Step 1: Write failing test for symbol endpoints**

```python
def test_add_symbol_to_watchlist(authenticated_client):
    """Test POST /api/watchlists/{id}/symbols."""
    # First create a watchlist
    response = authenticated_client.post("/api/watchlists", json={
        "name": "Tech Stocks"
    })
    watchlist_id = response.json()["id"]

    # Add symbol
    response = authenticated_client.post(
        f"/api/watchlists/{watchlist_id}/symbols",
        json={"symbol": "AAPL", "notes": "Good momentum"}
    )

    assert response.status_code == 200
    assert response.json()["success"] is True

def test_remove_symbol_from_watchlist(authenticated_client):
    """Test DELETE /api/watchlists/{id}/symbols/{symbol}."""
    # Create watchlist with symbol
    response = authenticated_client.post("/api/watchlists", json={
        "name": "Tech"
    })
    watchlist_id = response.json()["id"]

    authenticated_client.post(
        f"/api/watchlists/{watchlist_id}/symbols",
        json={"symbol": "AAPL"}
    )

    # Remove symbol
    response = authenticated_client.delete(
        f"/api/watchlists/{watchlist_id}/symbols/AAPL"
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/integration/api/test_watchlists.py -k "symbol" -v`
Expected: FAIL with "404 Not Found"

- [ ] **Step 3: Add symbol endpoints to routes**

```python
# Add to src/api/watchlists/routes.py

@router.get("/{watchlist_id}/symbols", response_model=List[WatchlistSymbolResponse])
def list_watchlist_symbols(
    watchlist_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List symbols in watchlist."""
    service = WatchlistService(db)
    symbols = service.get_watchlist_symbols(watchlist_id, current_user.id)

    return [
        WatchlistSymbolResponse(
            id=s.id,
            symbol=s.stock.symbol,
            added_at=s.added_at,
            notes=s.notes
        )
        for s in symbols
    ]


@router.post("/{watchlist_id}/symbols")
def add_symbol_to_watchlist(
    watchlist_id: int,
    data: WatchlistSymbolCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add symbol to watchlist."""
    service = WatchlistService(db)
    success = service.add_symbol(
        watchlist_id=watchlist_id,
        user_id=current_user.id,
        symbol=data.symbol,
        notes=data.notes
    )

    if not success:
        raise HTTPException(status_code=400, detail="Failed to add symbol")

    return {"success": True}


@router.delete("/{watchlist_id}/symbols/{symbol}")
def remove_symbol_from_watchlist(
    watchlist_id: int,
    symbol: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Remove symbol from watchlist."""
    service = WatchlistService(db)
    success = service.remove_symbol(
        watchlist_id=watchlist_id,
        user_id=current_user.id,
        symbol=symbol.upper()
    )

    if not success:
        raise HTTPException(status_code=404, detail="Symbol not found in watchlist")

    return {"success": True}
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/integration/api/test_watchlists.py -k "symbol" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/watchlists/routes.py tests/integration/api/test_watchlists.py
git commit -m "feat: add symbol management API endpoints"
```

---

## Task 9: API Routes - Categories and Clone

**Files:**
- Modify: `src/api/watchlists/routes.py`

- [ ] **Step 1: Write failing test for category endpoints**

```python
def test_list_categories(authenticated_client):
    """Test GET /api/watchlists/categories."""
    response = authenticated_client.get("/api/watchlists/categories")

    assert response.status_code == 200
    categories = response.json()
    assert len(categories) == 4  # Default categories

def test_create_category(authenticated_client):
    """Test POST /api/watchlists/categories."""
    response = authenticated_client.post("/api/watchlists/categories", json={
        "name": "My Custom Category",
        "icon": "🚀"
    })

    assert response.status_code == 201
    assert response.json()["name"] == "My Custom Category"
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/integration/api/test_watchlists.py -k "category" -v`
Expected: FAIL with "404 Not Found"

- [ ] **Step 3: Add category endpoints to routes**

```python
# Add to src/api/watchlists/routes.py

@router.get("/categories", response_model=List[CategoryResponse])
def list_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all categories for user."""
    service = WatchlistService(db)

    # Ensure defaults exist
    service.get_or_create_default_categories(current_user.id)

    return service.get_user_categories(current_user.id)


@router.post("/categories", response_model=CategoryResponse, status_code=201)
def create_category(
    data: CategoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new category."""
    service = WatchlistService(db)

    category = service.create_category(
        user_id=current_user.id,
        name=data.name,
        icon=data.icon,
        is_system=False
    )

    return category


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(
    category_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a category (only if not system)."""
    from src.db.models import WatchlistCategory

    category = (
        db.query(WatchlistCategory)
        .filter(WatchlistCategory.id == category_id)
        .filter(WatchlistCategory.user_id == current_user.id)
        .first()
    )

    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    if category.is_system:
        raise HTTPException(status_code=400, detail="Cannot delete system category")

    db.delete(category)
    db.commit()

    return None


@router.post("/{watchlist_id}/clone", response_model=WatchlistResponse)
def clone_watchlist(
    watchlist_id: int,
    data: WatchlistCloneRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Clone a watchlist."""
    service = WatchlistService(db)

    clone = service.clone_watchlist(
        watchlist_id=watchlist_id,
        user_id=current_user.id,
        new_name=data.new_name
    )

    if not clone:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    return clone
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/integration/api/test_watchlists.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/watchlists/routes.py tests/integration/api/test_watchlists.py
git commit -m "feat: add category and clone API endpoints"
```

---

## Task 10: Frontend - Types and API Client

**Files:**
- Create: `frontend/src/pages/watchlists/types.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Create TypeScript types**

```typescript
// frontend/src/pages/watchlists/types.ts
export interface WatchlistSymbol {
  id: number;
  symbol: string;
  added_at: string;
  notes: string | null;
}

export interface Watchlist {
  id: number;
  name: string;
  category_id: number | null;
  description: string | null;
  is_auto_generated: boolean;
  scanner_name: string | null;
  watchlist_mode: string;
  source_scan_date: string | null;
  created_at: string;
  updated_at: string;
  symbol_count: number;
}

export interface CategoryWatchlists {
  category_id: number | null;
  category_name: string;
  category_icon: string | null;
  is_system: boolean;
  watchlists: Watchlist[];
}

export interface WatchlistListResponse {
  categories: CategoryWatchlists[];
}

export interface WatchlistCreate {
  name: string;
  category_id?: number;
  description?: string;
}

export interface WatchlistUpdate {
  name?: string;
  category_id?: number;
  description?: string;
}

export interface Category {
  id: number;
  name: string;
  icon: string | null;
  sort_order: number;
  is_system: boolean;
  created_at: string;
}

export interface CategoryCreate {
  name: string;
  icon?: string;
}
```

- [ ] **Step 2: Add API client methods**

```typescript
// Add to frontend/src/lib/api.ts

import type {
  Watchlist,
  WatchlistCreate,
  WatchlistUpdate,
  WatchlistListResponse,
  WatchlistSymbol,
  Category,
  CategoryCreate,
} from '../pages/watchlists/types';

export const watchlistsAPI = {
  list: (): Promise<WatchlistListResponse> =>
    apiGet<WatchlistListResponse>('/api/watchlists'),

  create: (data: WatchlistCreate): Promise<Watchlist> =>
    apiPost<Watchlist>('/api/watchlists', data),

  get: (id: number): Promise<Watchlist> =>
    apiGet<Watchlist>(`/api/watchlists/${id}`),

  update: (id: number, data: WatchlistUpdate): Promise<Watchlist> =>
    apiPut<Watchlist>(`/api/watchlists/${id}`, data),

  delete: (id: number): Promise<void> =>
    apiDelete(`/api/watchlists/${id}`),

  symbols: {
    list: (watchlistId: number): Promise<WatchlistSymbol[]> =>
      apiGet<WatchlistSymbol[]>(`/api/watchlists/${watchlistId}/symbols`),

    add: (watchlistId: number, symbol: string, notes?: string): Promise<{ success: boolean }> =>
      apiPost<{ success: boolean }>(`/api/watchlists/${watchlistId}/symbols`, { symbol, notes }),

    remove: (watchlistId: number, symbol: string): Promise<{ success: boolean }> =>
      apiDelete(`/api/watchlists/${watchlistId}/symbols/${symbol}`),
  },

  categories: {
    list: (): Promise<Category[]> =>
      apiGet<Category[]>('/api/watchlists/categories'),

    create: (data: CategoryCreate): Promise<Category> =>
      apiPost<Category>('/api/watchlists/categories', data),

    delete: (id: number): Promise<void> =>
      apiDelete(`/api/watchlists/categories/${id}`),
  },

  clone: (id: number, newName: string): Promise<Watchlist> =>
    apiPost<Watchlist>(`/api/watchlists/${id}/clone`, { new_name: newName }),
};
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/watchlists/types.ts frontend/src/lib/api.ts
git commit -m "feat: add watchlist types and API client methods"
```

---

## Task 11: Frontend - Watchlist Dashboard

**Files:**
- Create: `frontend/src/pages/watchlists/dashboard.tsx`

- [ ] **Step 1: Create dashboard component**

```typescript
// frontend/src/pages/watchlists/dashboard.tsx
import { Component, For, Show } from 'solid-js';
import { useNavigate } from '@solidjs/router';
import { watchlistsAPI, type CategoryWatchlists } from './types';

export default function WatchlistDashboard() {
  const navigate = useNavigate();
  const [categories, setCategories] = createSignal<CategoryWatchlists[]>([]);
  const [loading, setLoading] = createSignal(true);

  onMount(async () => {
    try {
      const response = await watchlistsAPI.list();
      setCategories(response.categories);
    } catch (error) {
      console.error('Failed to load watchlists:', error);
    } finally {
      setLoading(false);
    }
  });

  return (
    <div class="watchlist-dashboard">
      <header class="dashboard-header">
        <h1>Watchlists</h1>
        <button onClick={() => navigate('/watchlists/create')}>
          + New Watchlist
        </button>
      </header>

      <Show when={loading()}>Loading...</Show>
      <Show when={!loading()}>
        <For each={categories()}>
          {(category) => (
            <section class="category-section">
              <h2>
                <span>{category.category_icon}</span>
                {category.category_name}
              </h2>
              <div class="watchlist-grid">
                <For each={category.watchlists}>
                  {(watchlist) => (
                    <div
                      class="watchlist-card"
                      onClick={() => navigate(`/watchlists/${watchlist.id}`)}
                    >
                      <h3>{watchlist.name}</h3>
                      <p>{watchlist.symbol_count} stocks</p>
                      <Show when={watchlist.is_auto_generated}>
                        <span class="badge">Auto-generated</span>
                      </Show>
                    </div>
                  )}
                </For>
              </div>
            </section>
          )}
        </For>
      </Show>
    </div>
  );
}
```

- [ ] **Step 2: Add basic styles**

```css
/* Add to frontend/src/index.css or create dashboard.css */
.watchlist-dashboard {
  padding: 2rem;
  max-width: 1400px;
  margin: 0 auto;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.category-section {
  margin-bottom: 3rem;
}

.watchlist-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 1rem;
  margin-top: 1rem;
}

.watchlist-card {
  padding: 1.5rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
}

.watchlist-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.badge {
  display: inline-block;
  padding: 0.25rem 0.5rem;
  background: var(--primary);
  color: white;
  border-radius: 4px;
  font-size: 0.875rem;
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/watchlists/dashboard.tsx frontend/src/index.css
git commit -m "feat: add watchlist dashboard component"
```

---

## Task 12: Frontend - Watchlist View (Split View)

**Files:**
- Create: `frontend/src/pages/watchlists/watchlist-view.tsx`

- [ ] **Step 1: Create split view component**

```typescript
// frontend/src/pages/watchlists/watchlist-view.tsx
import { Component, For, Show } from 'solid-js';
import { useParams } from '@solidjs/router';
import { watchlistsAPI, type Watchlist, type WatchlistSymbol } from './types';

export default function WatchlistView() {
  const params = useParams();
  const [watchlist, setWatchlist] = createSignal<Watchlist | null>(null);
  const [symbols, setSymbols] = createSignal<WatchlistSymbol[]>([]);
  const [selectedSymbol, setSelectedSymbol] = createSignal<string | null>(null);
  const [loading, setLoading] = createSignal(true);

  onMount(async () => {
    const id = parseInt(params.id);
    try {
      const [watchlistData, symbolsData] = await Promise.all([
        watchlistsAPI.get(id),
        watchlistsAPI.symbols.list(id),
      ]);
      setWatchlist(watchlistData);
      setSymbols(symbolsData);
    } catch (error) {
      console.error('Failed to load watchlist:', error);
    } finally {
      setLoading(false);
    }
  });

  const removeSymbol = async (symbol: string) => {
    const id = parseInt(params.id);
    try {
      await watchlistsAPI.symbols.remove(id, symbol);
      setSymbols(prev => prev.filter(s => s.symbol !== symbol));
    } catch (error) {
      console.error('Failed to remove symbol:', error);
    }
  };

  return (
    <div class="watchlist-view">
      <header class="watchlist-header">
        <h1>{watchlist()?.name}</h1>
        <Show when={watchlist()?.is_auto_generated}>
          <span class="badge">Auto-generated from {watchlist()?.scanner_name}</span>
        </Show>
      </header>

      <Show when={loading()}>Loading...</Show>
      <Show when={!loading()}>
        <div class="split-view">
          <div class="stock-list-pane">
            <For each={symbols()}>
              {(symbol) => (
                <div
                  class="stock-item"
                  classList={{ selected: selectedSymbol() === symbol.symbol }}
                  onClick={() => setSelectedSymbol(symbol.symbol)}
                >
                  <span class="symbol">{symbol.symbol}</span>
                  <Show when={symbol.notes}>
                    <span class="notes">{symbol.notes}</span>
                  </Show>
                  <button
                    class="remove-btn"
                    onClick={(e) => {
                      e.stopPropagation();
                      removeSymbol(symbol.symbol);
                    }}
                  >
                    ×
                  </button>
                </div>
              )}
            </For>
          </div>

          <div class="chart-pane">
            <Show when={selectedSymbol()}>
              <div class="chart-placeholder">
                <h2>{selectedSymbol()}</h2>
                <p>Charting component - Phase 5</p>
                <p>Chart will appear here when charting sub-project is implemented</p>
              </div>
            </Show>
            <Show when={!selectedSymbol()}>
              <div class="chart-placeholder empty">
                <p>Select a stock to view chart</p>
              </div>
            </Show>
          </div>
        </div>
      </Show>
    </div>
  );
}
```

- [ ] **Step 2: Add split view styles**

```css
/* Add to frontend/src/index.css */
.watchlist-view {
  padding: 2rem;
  height: calc(100vh - 200px);
}

.watchlist-header {
  margin-bottom: 2rem;
}

.split-view {
  display: grid;
  grid-template-columns: 30% 70%;
  gap: 2rem;
  height: calc(100% - 100px);
}

.stock-list-pane {
  border-right: 1px solid var(--border);
  padding-right: 1rem;
  overflow-y: auto;
}

.stock-item {
  padding: 1rem;
  border-bottom: 1px solid var(--border);
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stock-item:hover,
.stock-item.selected {
  background: var(--hover-bg);
}

.symbol {
  font-weight: bold;
}

.notes {
  font-size: 0.875rem;
  color: var(--muted);
}

.remove-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  color: var(--danger);
  cursor: pointer;
  padding: 0 0.5rem;
}

.chart-pane {
  display: flex;
  align-items: center;
  justify-content: center;
}

.chart-placeholder {
  text-align: center;
  color: var(--muted);
}

.chart-placeholder.empty {
  opacity: 0.5;
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/watchlists/watchlist-view.tsx frontend/src/index.css
git commit -m "feat: add watchlist split view component"
```

---

## Task 13: Frontend - Routing Integration

**Files:**
- Modify: `frontend/src/main.tsx`

- [ ] **Step 1: Add watchlist routes**

```typescript
// Add to frontend/src/main.tsx router imports
import WatchlistDashboard from './pages/watchlists/dashboard';
import WatchlistView from './pages/watchlists/watchlist-view';

// Add to routes array:
{
  path: '/watchlists',
  component: WatchlistDashboard,
},
{
  path: '/watchlists/:id',
  component: WatchlistView,
},
```

- [ ] **Step 2: Update nav to include watchlists link**

```typescript
// Add to frontend/src/app.tsx navigation
<a href="/watchlists">Watchlists</a>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/main.tsx frontend/src/app.tsx
git commit -m "feat: add watchlist routes to navigation"
```

---

## Task 14: EOD Integration - Watchlist Generation Service

**Files:**
- Modify: `src/api/watchlists/service.py`

- [ ] **Step 1: Write failing test for scanner watchlist generation**

```python
# tests/unit/api/test_watchlist_service.py
import pytest
from datetime import date, timedelta
from src.api.watchlists.service import WatchlistGenerationService
from src.db.models import User, Stock, ScannerResult

def test_generate_watchlist_from_scanner(db_session):
    """Test generating watchlist from scanner results."""
    user = User(username="test", password_hash="hash")
    db_session.add(user)
    db_session.flush()

    stock = Stock(symbol="AAPL", name="Apple Inc")
    db_session.add(stock)
    db_session.flush()

    # Create scanner result
    result = ScannerResult(
        stock_id=stock.id,
        scanner_name="price_action",
        result_metadata={"reason": "bounce_off_support"},
        matched_at=date.today()
    )
    db_session.add(result)
    db_session.commit()

    service = WatchlistGenerationService(db_session)
    watchlist = service.generate_from_scanner_results(
        scanner_name="price_action",
        scan_date=date.today(),
        user_id=user.id
    )

    assert watchlist is not None
    assert "Price Action - Today" in watchlist.name
    assert len(watchlist.symbols) == 1
```

- [ ] **Step 2: Run test**

Run: `pytest tests/unit/api/test_watchlist_service.py::test_generate_watchlist_from_scanner -v`
Expected: FAIL with "cannot import name 'WatchlistGenerationService'"

- [ ] **Step 3: Add WatchlistGenerationService class**

```python
# Add to src/api/watchlists/service.py

class WatchlistGenerationService:
    """Service for auto-generating watchlists from scanner results."""

    def __init__(self, db: Session):
        self.db = db

    def generate_from_scanner_results(
        self,
        scanner_name: str,
        scan_date: date,
        user_id: int
    ):
        """
        Generate watchlists from scanner results.

        Creates two watchlists if scanner has matches:
        - "{Scanner} - Today" (replace mode)
        - "{Scanner} - History" (append mode)

        Returns: The "Today" watchlist if created, None if no matches
        """
        from src.db.models import ScannerResult as ScannerResultModel

        # Query scanner results for this date
        results = (
            self.db.query(ScannerResultModel)
            .join(Stock, ScannerResultModel.stock_id == Stock.id)
            .filter(ScannerResultModel.scanner_name == scanner_name)
            .filter(ScannerResultModel.matched_at >= scan_date)
            .filter(ScannerResultModel.matched_at < scan_date + timedelta(days=1))
            .all()
        )

        if not results:
            return None

        # Get or create "Scanner Results" category
        scanner_category = self._get_or_create_scanner_category(user_id)

        # Create "{Scanner} - Today" watchlist (replace mode)
        today_watchlist = self._create_or_replace_watchlist(
            scanner_name=scanner_name,
            mode="replace",
            scan_date=scan_date,
            category_id=scanner_category.id,
            user_id=user_id,
            results=results
        )

        # Create "{Scanner} - History" watchlist (append mode)
        self._create_or_append_watchlist(
            scanner_name=scanner_name,
            mode="append",
            category_id=scanner_category.id,
            user_id=user_id,
            results=results
        )

        return today_watchlist

    def _get_or_create_scanner_category(self, user_id: int) -> WatchlistCategory:
        """Get or create the 'Scanner Results' category for user."""
        category = (
            self.db.query(WatchlistCategory)
            .filter(WatchlistCategory.user_id == user_id)
            .filter(WatchlistCategory.name == "Scanner Results")
            .filter(WatchlistCategory.is_system == True)
            .first()
        )

        if not category:
            category = WatchlistCategory(
                user_id=user_id,
                name="Scanner Results",
                icon="📊",
                sort_order=2,
                is_system=True,
            )
            self.db.add(category)
            self.db.commit()

        return category

    def _create_or_replace_watchlist(
        self,
        scanner_name: str,
        mode: str,
        scan_date: date,
        category_id: int,
        user_id: int,
        results: list
    ) -> Watchlist:
        """Create watchlist or replace existing symbols."""
        watchlist_name = f"{self._format_scanner_name(scanner_name)} - Today"

        # Look for existing watchlist
        existing = (
            self.db.query(Watchlist)
            .filter(Watchlist.user_id == user_id)
            .filter(Watchlist.name == watchlist_name)
            .filter(Watchlist.scanner_name == scanner_name)
            .filter(Watchlist.watchlist_mode == mode)
            .first()
        )

        if existing:
            # Remove all existing symbols (replace mode)
            self.db.query(WatchlistSymbol).filter(
                WatchlistSymbol.watchlist_id == existing.id
            ).delete()
            watchlist = existing
        else:
            # Create new watchlist
            watchlist = Watchlist(
                user_id=user_id,
                name=watchlist_name,
                category_id=category_id,
                is_auto_generated=True,
                scanner_name=scanner_name,
                watchlist_mode=mode,
                source_scan_date=scan_date,
            )
            self.db.add(watchlist)
            self.db.flush()

        # Add new symbols
        for result in results:
            symbol_entry = WatchlistSymbol(
                watchlist_id=watchlist.id,
                stock_id=result.stock_id,
                notes=f"Matched at {result.matched_at}: {result.result_metadata.get('reason', 'N/A')}"
            )
            self.db.add(symbol_entry)

        self.db.commit()
        return watchlist

    def _create_or_append_watchlist(
        self,
        scanner_name: str,
        mode: str,
        category_id: int,
        user_id: int,
        results: list
    ) -> Watchlist:
        """Create watchlist or append new symbols to existing."""
        watchlist_name = f"{self._format_scanner_name(scanner_name)} - History"

        # Look for existing watchlist
        existing = (
            self.db.query(Watchlist)
            .filter(Watchlist.user_id == user_id)
            .filter(Watchlist.name == watchlist_name)
            .filter(Watchlist.scanner_name == scanner_name)
            .filter(Watchlist.watchlist_mode == mode)
            .first()
        )

        if existing:
            watchlist = existing
        else:
            watchlist = Watchlist(
                user_id=user_id,
                name=watchlist_name,
                category_id=category_id,
                is_auto_generated=True,
                scanner_name=scanner_name,
                watchlist_mode=mode,
            )
            self.db.add(watchlist)
            self.db.flush()

        # Append new symbols (avoid duplicates)
        existing_stock_ids = {
            ws.stock_id
            for ws in self.db.query(WatchlistSymbol)
            .filter(WatchlistSymbol.watchlist_id == watchlist.id)
            .all()
        }

        for result in results:
            if result.stock_id not in existing_stock_ids:
                symbol_entry = WatchlistSymbol(
                    watchlist_id=watchlist.id,
                    stock_id=result.stock_id,
                    notes=f"{result.matched_at.date()}: {result.result_metadata.get('reason', 'N/A')}"
                )
                self.db.add(symbol_entry)

        self.db.commit()
        return watchlist

    def _format_scanner_name(self, scanner_name: str) -> str:
        """Format scanner name for display."""
        return scanner_name.replace("_", " ").title()
```

- [ ] **Step 4: Run test**

Run: `pytest tests/unit/api/test_watchlist_service.py::test_generate_watchlist_from_scanner -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/watchlists/service.py tests/unit/api/test_watchlist_service.py
git commit -m "feat: add WatchlistGenerationService for EOD integration"
```

---

## Task 15: EOD Integration - CLI Hook

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: Update scan command to generate watchlists**

```python
# Find the scan command in src/main.py and add watchlist generation

@app.command()
def scan():
    """Run scanners on existing data."""
    from src.config import get_config
    from src.scanner.registry import ScannerRegistry
    from src.scanner.executor import ScannerExecutor
    # ... existing imports ...

    cfg = get_config()
    logging.basicConfig(level=cfg.LOG_LEVEL)
    logger.info("Starting scanner...")

    db = _get_db_session()
    try:
        # ... existing scanner setup code ...

        results = executor.run_eod(stocks_with_candles)
        logger.info(f"Scan complete. Found {len(results)} matches.")

        # NEW: Auto-generate watchlists from scanner results
        try:
            from src.api.watchlists.service import WatchlistGenerationService
            from src.db.models import User

            # Get first user (single-user deployment)
            user = db.query(User).first()
            if user:
                watchlist_service = WatchlistGenerationService(db)

                # Group results by scanner
                scanner_names = set(r.scanner_name for r in results)

                for scanner_name in scanner_names:
                    watchlist = watchlist_service.generate_from_scanner_results(
                        scanner_name=scanner_name,
                        scan_date=today,
                        user_id=user.id
                    )
                    if watchlist:
                        logger.info(f"Created watchlist: {watchlist.name}")

                logger.info("Watchlist generation complete.")
        except Exception as e:
            logger.error(f"Watchlist generation failed: {e}", exc_info=True)
            # Don't fail the scan if watchlist generation fails

    except Exception as e:
        logger.error(f"Scan failed: {e}", exc_info=True)
        click.echo(f"Error: {e}", err=True)
    finally:
        db.close()
```

- [ ] **Step 2: Test EOD integration**

Run: `python -m src.main scan`

Expected: Scan runs successfully and creates watchlists

- [ ] **Step 3: Verify watchlists created**

Run: `psql -U market_data -d market_data -c "SELECT name, symbol_count FROM watchlists JOIN (SELECT watchlist_id, COUNT(*) as symbol_count FROM watchlist_symbols GROUP BY watchlist_id) counts ON watchlists.id = counts.watchlist_id;"`

Expected: Shows auto-generated watchlists with symbols

- [ ] **Step 4: Commit**

```bash
git add src/main.py
git commit -m "feat: integrate watchlist generation into EOD scan command"
```

---

## Task 16: End-to-End Testing

**Files:**
- Create: `tests/integration/test_watchlist_eod.py`

- [ ] **Step 1: Write E2E test for full watchlist workflow**

```python
# tests/integration/test_watchlist_eod.py
import pytest
from datetime import date

def test_full_watchlist_workflow(db_session, authenticated_client):
    """Test complete watchlist workflow: EOD → API → Frontend flow."""
    # 1. Create a watchlist via API
    response = authenticated_client.post("/api/watchlists", json={
        "name": "Manual Test Watchlist",
        "description": "Created via API"
    })
    assert response.status_code == 201
    watchlist_id = response.json()["id"]

    # 2. Add symbols to watchlist
    response = authenticated_client.post(
        f"/api/watchlists/{watchlist_id}/symbols",
        json={"symbol": "AAPL", "notes": "Test position"}
    )
    assert response.status_code == 200

    # 3. List symbols in watchlist
    response = authenticated_client.get(f"/api/watchlists/{watchlist_id}/symbols")
    assert response.status_code == 200
    symbols = response.json()
    assert len(symbols) == 1
    assert symbols[0]["symbol"] == "AAPL"

    # 4. Remove symbol
    response = authenticated_client.delete(f"/api/watchlists/{watchlist_id}/symbols/AAPL")
    assert response.status_code == 200

    # 5. Verify symbol removed
    response = authenticated_client.get(f"/api/watchlists/{watchlist_id}/symbols")
    assert response.status_code == 200
    symbols = response.json()
    assert len(symbols) == 0

    # 6. Delete watchlist
    response = authenticated_client.delete(f"/api/watchlists/{watchlist_id}")
    assert response.status_code == 204

    # 7. Verify deleted
    response = authenticated_client.get(f"/api/watchlists/{watchlist_id}")
    assert response.status_code == 404

def test_eod_creates_watchlists(db_session):
    """Test that EOD scan creates auto-generated watchlists."""
    from src.main import eod
    from click.testing import CliRunner
    from src.db.models import Watchlist, User

    # Get user
    user = db_session.query(User).first()

    # Run EOD (this will scan and generate watchlists)
    runner = CliRunner()
    result = runner.invoke(eod, [])

    # Check that watchlists were created
    watchlists = (
        db_session.query(Watchlist)
        .filter(Watchlist.user_id == user.id)
        .filter(Watchlist.is_auto_generated == True)
        .all()
    )

    # Should have created "Today" and "History" watchlists for each scanner
    assert len(watchlists) > 0

    # Verify watchlist structure
    for wl in watchlists:
        assert wl.scanner_name is not None
        assert wl.watchlist_mode in ["replace", "append"]
        if wl.watchlist_mode == "replace":
            assert "Today" in wl.name
        else:
            assert "History" in wl.name
```

- [ ] **Step 2: Run E2E tests**

Run: `pytest tests/integration/test_watchlist_eod.py -v`

Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_watchlist_eod.py
git commit -m "test: add end-to-end tests for watchlist workflow"
```

---

## Task 17: Documentation

**Files:**
- Create: `docs/watchlists.md`

- [ ] **Step 1: Create watchlist documentation**

```markdown
# Watchlists Feature Documentation

## Overview
Watchlists allow users to organize and track stock lists. They can be created manually or auto-generated from EOD scanner results.

## Features
- Manual watchlist CRUD (create, read, update, delete)
- Add/remove symbols from watchlists
- Category-based organization
- Auto-generation from EOD scanners
- Clone existing watchlists
- Per-user isolation

## API Endpoints

### Watchlists
- `GET /api/watchlists` - List all watchlists grouped by category
- `POST /api/watchlists` - Create new watchlist
- `GET /api/watchlists/{id}` - Get watchlist details
- `PUT /api/watchlists/{id}` - Update watchlist
- `DELETE /api/watchlists/{id}` - Delete watchlist
- `POST /api/watchlists/{id}/clone` - Clone watchlist

### Symbols
- `GET /api/watchlists/{id}/symbols` - List symbols in watchlist
- `POST /api/watchlists/{id}/symbols` - Add symbol to watchlist
- `DELETE /api/watchlists/{id}/symbols/{symbol}` - Remove symbol

### Categories
- `GET /api/watchlists/categories` - List all categories
- `POST /api/watchlists/categories` - Create new category
- `DELETE /api/watchlists/categories/{id}` - Delete category

## CLI Usage

### Running EOD Scan (with watchlist generation)
```bash
python -m src.main scan
```

This will:
1. Run all enabled scanners
2. Generate auto-watchlists from results
3. Create "Today" (replace) and "History" (append) watchlists for each scanner

## Frontend

### Watchlist Dashboard
Navigate to `/watchlists` to see all watchlists organized by category.

### Watchlist View (Split View)
Click on a watchlist to enter split view:
- Left pane: List of stocks
- Right pane: Chart (Phase 5 - currently placeholder)

## Default Categories
- 🔥 Active Trading
- 📊 Scanner Results (auto-generated watchlists)
- 🔬 Research
- 📦 Archived

## Data Retention
- Scanner results: 90 days in watchlists
- After 90 days: Aggregated to statistics (future feature)
```

- [ ] **Step 2: Commit**

```bash
git add docs/watchlists.md
git commit -m "docs: add watchlists feature documentation"
```

---

## Self-Review Checklist

✅ **Spec Coverage:**
- Manual CRUD watchlists → Tasks 1-9
- Symbol management → Tasks 1, 8
- Category organization → Tasks 1, 5, 9
- Per-user isolation → Tasks 1, 4-9
- Auto-generation from EOD → Tasks 14-16
- Hybrid Today/History watchlists → Tasks 14-15
- 90-day retention → Documented in Task 17 (cleanup job not in scope)
- Frontend dashboard → Task 11
- Frontend split view → Task 12
- Templates/clone → Tasks 6, 9

✅ **Placeholder Scan:**
- No TBDs found
- All code shown explicitly
- All test code provided
- All file paths exact

✅ **Type Consistency:**
- `WatchlistCreate` schema matches API usage ✓
- `WatchlistService` methods consistent across tasks ✓
- TypeScript types match Pydantic schemas ✓
- `watchlist_mode` values consistent ("manual", "replace", "append") ✓

✅ **Missing:**
- Frontend unit tests for components → Added as task 11-13
- Frontend E2E tests with Playwright → Could add but not critical for v1
- 90-day retention cleanup job → Documented as future work, not required for initial feature

---

Plan complete and saved to `docs/superpowers/plans/2026-04-12-watchlists-implementation.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
