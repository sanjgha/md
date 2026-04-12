"""Watchlist service layer with business logic for CRUD operations."""

from datetime import date, timedelta
from typing import List, Optional, cast

from sqlalchemy.orm import Session

from src.db.models import (
    Stock,
    Watchlist,
    WatchlistCategory,
    WatchlistSymbol,
)


class WatchlistService:
    """Service layer for watchlist business logic."""

    def __init__(self, db_session: Session):
        """Initialize the service with a database session.

        Args:
            db_session: SQLAlchemy Session for database operations
        """
        self.db_session = db_session

    def create_watchlist(
        self,
        user_id: int,
        name: str,
        description: Optional[str] = None,
        category_id: Optional[int] = None,
    ) -> Watchlist:
        """Create a new watchlist for a user.

        Args:
            user_id: ID of the user creating the watchlist
            name: Name of the watchlist
            description: Optional description
            category_id: Optional category ID

        Returns:
            Created Watchlist instance
        """
        watchlist = Watchlist(
            user_id=user_id,
            name=name,
            description=description,
            category_id=category_id,
            is_auto_generated=False,
            watchlist_mode="static",
        )
        self.db_session.add(watchlist)
        self.db_session.commit()
        self.db_session.refresh(watchlist)
        return watchlist

    def get_user_watchlists(self, user_id: int) -> List[Watchlist]:
        """Get all watchlists for a user, ordered by creation date desc.

        Args:
            user_id: ID of the user

        Returns:
            List of Watchlist instances ordered by created_at desc
        """
        return (
            self.db_session.query(Watchlist)
            .filter(Watchlist.user_id == user_id)
            .order_by(Watchlist.created_at.desc())
            .all()
        )

    def get_watchlist(self, watchlist_id: int, user_id: int) -> Optional[Watchlist]:
        """Get a watchlist by ID if owned by the user.

        Args:
            watchlist_id: ID of the watchlist
            user_id: ID of the user requesting the watchlist

        Returns:
            Watchlist instance if found and owned by user, None otherwise
        """
        return (
            self.db_session.query(Watchlist)
            .filter(Watchlist.id == watchlist_id, Watchlist.user_id == user_id)
            .first()
        )

    def update_watchlist(
        self,
        watchlist_id: int,
        user_id: int,
        **kwargs,
    ) -> Optional[Watchlist]:
        """Update a watchlist if owned by the user.

        Args:
            watchlist_id: ID of the watchlist to update
            user_id: ID of the user requesting the update
            **kwargs: Fields to update (name, description, category_id)

        Returns:
            Updated Watchlist instance if found and owned, None otherwise
        """
        watchlist = self.get_watchlist(watchlist_id, user_id)
        if not watchlist:
            return None

        # Update only allowed fields; category_id explicitly allows None (to unassign)
        allowed_fields = {"name", "description", "category_id"}
        for field, value in kwargs.items():
            if field not in allowed_fields:
                continue
            if field == "category_id" or value is not None:
                setattr(watchlist, field, value)

        self.db_session.commit()
        self.db_session.refresh(watchlist)
        return watchlist

    def delete_watchlist(self, watchlist_id: int, user_id: int) -> bool:
        """Delete a watchlist if owned by the user.

        Args:
            watchlist_id: ID of the watchlist to delete
            user_id: ID of the user requesting the deletion

        Returns:
            True if deleted, False if not found or not owned
        """
        watchlist = self.get_watchlist(watchlist_id, user_id)
        if not watchlist:
            return False

        self.db_session.delete(watchlist)
        self.db_session.commit()
        return True

    def add_symbol(
        self,
        watchlist_id: int,
        user_id: int,
        symbol: str,
        notes: Optional[str] = None,
    ) -> Optional[WatchlistSymbol]:
        """Add a symbol to a watchlist.

        Args:
            watchlist_id: ID of the watchlist
            user_id: ID of the user requesting the addition
            symbol: Stock symbol to add (must exist in stocks table)
            notes: Optional notes for the symbol

        Returns:
            Created WatchlistSymbol instance if successful, None if:
            - Watchlist not found or not owned by user
            - Stock symbol doesn't exist in stocks table
            - Symbol already exists in the watchlist (duplicate)
        """
        # Verify watchlist ownership
        watchlist = self.get_watchlist(watchlist_id, user_id)
        if not watchlist:
            return None

        # Verify stock exists
        stock = self.db_session.query(Stock).filter(Stock.symbol == symbol.upper()).first()
        if not stock:
            return None

        # Check for duplicate
        existing = (
            self.db_session.query(WatchlistSymbol)
            .filter(
                WatchlistSymbol.watchlist_id == watchlist_id,
                WatchlistSymbol.stock_id == stock.id,
            )
            .first()
        )
        if existing:
            return None

        # Create and return the symbol
        watchlist_symbol = WatchlistSymbol(
            watchlist_id=watchlist_id,
            stock_id=stock.id,
            notes=notes,
        )
        self.db_session.add(watchlist_symbol)
        self.db_session.commit()
        self.db_session.refresh(watchlist_symbol)
        return watchlist_symbol

    def remove_symbol(
        self,
        watchlist_id: int,
        user_id: int,
        symbol: str,
    ) -> bool:
        """Remove a symbol from a watchlist.

        Args:
            watchlist_id: ID of the watchlist
            user_id: ID of the user requesting the removal
            symbol: Stock symbol to remove

        Returns:
            True if removed, False if:
            - Watchlist not found or not owned by user
            - Symbol not found in the watchlist
        """
        # Verify watchlist ownership
        watchlist = self.get_watchlist(watchlist_id, user_id)
        if not watchlist:
            return False

        # Find the stock
        stock = self.db_session.query(Stock).filter(Stock.symbol == symbol.upper()).first()
        if not stock:
            return False

        # Find and delete the symbol
        watchlist_symbol = (
            self.db_session.query(WatchlistSymbol)
            .filter(
                WatchlistSymbol.watchlist_id == watchlist_id,
                WatchlistSymbol.stock_id == stock.id,
            )
            .first()
        )
        if not watchlist_symbol:
            return False

        self.db_session.delete(watchlist_symbol)
        self.db_session.commit()
        return True

    def get_watchlist_symbols(
        self,
        watchlist_id: int,
        user_id: int,
    ) -> List[WatchlistSymbol]:
        """Get all symbols in a watchlist with stock information.

        Args:
            watchlist_id: ID of the watchlist
            user_id: ID of the user requesting the symbols

        Returns:
            List of WatchlistSymbol instances with loaded Stock relationships,
            ordered by priority. Returns empty list if watchlist not found or
            not owned by user.
        """
        # Verify watchlist ownership
        watchlist = self.get_watchlist(watchlist_id, user_id)
        if not watchlist:
            return []

        # Query symbols with stock info, ordered by priority
        symbols = (
            self.db_session.query(WatchlistSymbol)
            .filter(WatchlistSymbol.watchlist_id == watchlist_id)
            .join(WatchlistSymbol.stock)
            .order_by(WatchlistSymbol.priority)
            .all()
        )
        return symbols

    def create_category(
        self,
        user_id: int,
        name: str,
        icon: Optional[str] = None,
        is_system: bool = False,
        description: Optional[str] = None,
        color: Optional[str] = None,
    ) -> WatchlistCategory:
        """Create a new category for a user.

        Args:
            user_id: ID of the user creating the category
            name: Name of the category
            icon: Emoji icon for the category (optional)
            is_system: Whether this is a system category (default False)
            description: Optional description
            color: Optional hex color code

        Returns:
            Created WatchlistCategory instance
        """
        # Convert empty string to None for icon
        icon_value = icon if icon else None

        category = WatchlistCategory(
            user_id=user_id,
            name=name,
            icon=icon_value,
            is_system=is_system,
            description=description,
            color=color,
            sort_order=0,  # Default sort order
        )
        self.db_session.add(category)
        self.db_session.commit()
        self.db_session.refresh(category)
        return category

    def get_or_create_default_categories(self, user_id: int) -> List[WatchlistCategory]:
        """Get or create default categories for a user.

        Creates 4 default categories if they don't exist:
        - Active Trading (🔥) - sort_order: 1
        - Scanner Results (📊) - sort_order: 2
        - Research (🔬) - sort_order: 3
        - Archived (📦) - sort_order: 4

        Args:
            user_id: ID of the user

        Returns:
            List of WatchlistCategory instances (default categories)
        """
        # Define default categories
        defaults = [
            {
                "name": "Active Trading",
                "icon": "🔥",
                "is_system": True,
                "sort_order": 1,
            },
            {
                "name": "Scanner Results",
                "icon": "📊",
                "is_system": True,
                "sort_order": 2,
            },
            {
                "name": "Research",
                "icon": "🔬",
                "is_system": True,
                "sort_order": 3,
            },
            {
                "name": "Archived",
                "icon": "📦",
                "is_system": True,
                "sort_order": 4,
            },
        ]

        # Get existing system categories for user
        existing_categories = (
            self.db_session.query(WatchlistCategory)
            .filter(
                WatchlistCategory.user_id == user_id,
                WatchlistCategory.is_system.is_(True),
            )
            .all()
        )

        # If all defaults exist (or more), return them
        if len(existing_categories) >= len(defaults):
            # Return them ordered by sort_order
            return sorted(existing_categories, key=lambda x: cast(int, x.sort_order))

        # Create missing default categories
        existing_names = {cat.name for cat in existing_categories}
        created_categories = []

        for default in defaults:
            if default["name"] not in existing_names:
                category = WatchlistCategory(
                    user_id=user_id,
                    name=default["name"],
                    icon=default["icon"],
                    is_system=default["is_system"],
                    sort_order=default["sort_order"],
                )
                self.db_session.add(category)
                created_categories.append(category)
            else:
                # Find existing category and add to result
                for cat in existing_categories:
                    if cat.name == default["name"]:
                        created_categories.append(cat)
                        break

        if created_categories:
            self.db_session.commit()
            # Refresh to get IDs
            for cat in created_categories:
                self.db_session.refresh(cat)

        # Return all default categories ordered by sort_order
        return sorted(created_categories, key=lambda x: cast(int, x.sort_order))

    def get_user_categories(self, user_id: int) -> List[WatchlistCategory]:
        """Get all categories for a user, ordered by sort_order.

        Args:
            user_id: ID of the user

        Returns:
            List of WatchlistCategory instances ordered by sort_order
        """
        return (
            self.db_session.query(WatchlistCategory)
            .filter(WatchlistCategory.user_id == user_id)
            .order_by(WatchlistCategory.sort_order)
            .all()
        )

    def clone_watchlist(
        self,
        watchlist_id: int,
        user_id: int,
        new_name: str,
    ) -> Optional[Watchlist]:
        """Clone a watchlist with all its symbols.

        Args:
            watchlist_id: ID of the watchlist to clone
            user_id: ID of the user requesting the clone
            new_name: Name for the cloned watchlist

        Returns:
            Cloned Watchlist instance if found and owned, None otherwise
        """
        # Get the original watchlist
        original = self.get_watchlist(watchlist_id, user_id)
        if not original:
            return None

        # Create the cloned watchlist
        cloned = Watchlist(
            user_id=user_id,
            name=new_name,
            description=original.description,
            category_id=original.category_id,
            is_auto_generated=False,  # Clones are never auto-generated
            watchlist_mode=original.watchlist_mode,
        )
        self.db_session.add(cloned)
        self.db_session.flush()  # Get the ID without committing

        # Copy all symbols from the original watchlist
        from src.db.models import WatchlistSymbol

        original_symbols = (
            self.db_session.query(WatchlistSymbol)
            .filter(WatchlistSymbol.watchlist_id == watchlist_id)
            .all()
        )

        for symbol in original_symbols:
            cloned_symbol = WatchlistSymbol(
                watchlist_id=cloned.id,
                stock_id=symbol.stock_id,
                notes=symbol.notes,
                priority=symbol.priority,
            )
            self.db_session.add(cloned_symbol)

        self.db_session.commit()
        self.db_session.refresh(cloned)
        return cloned

    def get_watchlists_grouped(self, user_id: int) -> List[dict]:
        """Get watchlists grouped by category with symbol counts.

        Args:
            user_id: ID of the user

        Returns:
            List of dicts with structure:
            {
                "category_id": int,
                "category_name": str,
                "category_icon": str,
                "is_system": bool,
                "watchlists": [
                    {
                        "id": int,
                        "name": str,
                        "description": str | None,
                        "symbol_count": int,
                        "created_at": datetime,
                        "updated_at": datetime,
                    }
                ]
            }
            Ordered by category sort_order
        """
        from src.db.models import WatchlistSymbol, WatchlistCategory

        # Get all categories for the user, ordered by sort_order
        categories = (
            self.db_session.query(WatchlistCategory)
            .filter(WatchlistCategory.user_id == user_id)
            .order_by(WatchlistCategory.sort_order)
            .all()
        )

        result = []

        for category in categories:
            # Get all watchlists in this category
            watchlists = (
                self.db_session.query(Watchlist)
                .filter(
                    Watchlist.user_id == user_id,
                    Watchlist.category_id == category.id,
                )
                .order_by(Watchlist.created_at.desc())
                .all()
            )

            # Build watchlist data with symbol counts
            watchlist_data = []
            for watchlist in watchlists:
                # Count symbols in this watchlist
                symbol_count = (
                    self.db_session.query(WatchlistSymbol)
                    .filter(WatchlistSymbol.watchlist_id == watchlist.id)
                    .count()
                )

                watchlist_data.append(
                    {
                        "id": watchlist.id,
                        "name": watchlist.name,
                        "description": watchlist.description,
                        "symbol_count": symbol_count,
                        "created_at": watchlist.created_at,
                        "updated_at": watchlist.updated_at,
                    }
                )

            # Add category with its watchlists
            result.append(
                {
                    "category_id": category.id,
                    "category_name": category.name,
                    "category_icon": category.icon or "",
                    "is_system": category.is_system,
                    "watchlists": watchlist_data,
                }
            )

        # Include watchlists with no category under a synthetic "Uncategorized" group
        uncategorized_watchlists = (
            self.db_session.query(Watchlist)
            .filter(
                Watchlist.user_id == user_id,
                Watchlist.category_id.is_(None),
            )
            .order_by(Watchlist.created_at.desc())
            .all()
        )

        if uncategorized_watchlists:
            uncategorized_data = []
            for watchlist in uncategorized_watchlists:
                symbol_count = (
                    self.db_session.query(WatchlistSymbol)
                    .filter(WatchlistSymbol.watchlist_id == watchlist.id)
                    .count()
                )
                uncategorized_data.append(
                    {
                        "id": watchlist.id,
                        "name": watchlist.name,
                        "description": watchlist.description,
                        "symbol_count": symbol_count,
                        "created_at": watchlist.created_at,
                        "updated_at": watchlist.updated_at,
                    }
                )
            result.append(
                {
                    "category_id": None,
                    "category_name": "Uncategorized",
                    "category_icon": "",
                    "is_system": False,
                    "watchlists": uncategorized_data,
                }
            )

        return result


class WatchlistGenerationService:
    """Service for auto-generating watchlists from scanner results."""

    def __init__(self, db: Session):
        """Initialize the service with a database session.

        Args:
            db: SQLAlchemy Session for database operations
        """
        self.db = db

    def generate_from_scanner_results(
        self,
        scanner_name: str,
        scan_date: date,
        user_id: int,
    ) -> Optional[Watchlist]:
        """Generate watchlists from scanner results.

        Creates two watchlists if scanner has matches:
        - "{Scanner} - Today" (replace mode)
        - "{Scanner} - History" (append mode)

        Args:
            scanner_name: Name of the scanner (e.g., "price_action", "momentum")
            scan_date: Date of the scan
            user_id: ID of the user to create watchlists for

        Returns:
            The "Today" watchlist if created, None if no matches
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
            category_id=cast(int, scanner_category.id),
            user_id=user_id,
            results=results,
        )

        # Create "{Scanner} - History" watchlist (append mode)
        self._create_or_append_watchlist(
            scanner_name=scanner_name,
            mode="append",
            category_id=cast(int, scanner_category.id),
            user_id=user_id,
            results=results,
        )

        return today_watchlist

    def _get_or_create_scanner_category(self, user_id: int) -> WatchlistCategory:
        """Get or create the 'Scanner Results' category for user.

        Args:
            user_id: ID of the user

        Returns:
            WatchlistCategory instance for "Scanner Results"
        """
        category = (
            self.db.query(WatchlistCategory)
            .filter(WatchlistCategory.user_id == user_id)
            .filter(WatchlistCategory.name == "Scanner Results")
            .filter(WatchlistCategory.is_system.is_(True))
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
        results: list,
    ) -> Watchlist:
        """Create watchlist or replace existing symbols.

        Args:
            scanner_name: Name of the scanner
            mode: Watchlist mode (e.g., "replace")
            scan_date: Date of the scan
            category_id: ID of the watchlist category
            user_id: ID of the user
            results: List of ScannerResult objects

        Returns:
            Created or updated Watchlist instance
        """
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
                notes=f"Matched at {result.matched_at}: {result.result_metadata.get('reason', 'N/A')}",
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
        results: list,
    ) -> Watchlist:
        """Create watchlist or append new symbols to existing.

        Args:
            scanner_name: Name of the scanner
            mode: Watchlist mode (e.g., "append")
            category_id: ID of the watchlist category
            user_id: ID of the user
            results: List of ScannerResult objects

        Returns:
            Created or updated Watchlist instance
        """
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
                    notes=f"{result.matched_at.date()}: {result.result_metadata.get('reason', 'N/A')}",
                )
                self.db.add(symbol_entry)

        self.db.commit()
        return watchlist

    def _format_scanner_name(self, scanner_name: str) -> str:
        """Format scanner name for display.

        Args:
            scanner_name: Raw scanner name (e.g., "price_action")

        Returns:
            Formatted name (e.g., "Price Action")
        """
        return scanner_name.replace("_", " ").title()
