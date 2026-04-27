"""Watchlist service layer with business logic for CRUD operations."""

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import List, Optional, cast

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.watchlists.schemas import (
    CategoryWatchlists,
    CategoryResponse,
    IntradayPoint,
    QuoteResponse,
    WatchlistSummary,
)
from src.db.models import (
    DailyCandle,
    IntradayCandle,
    RealtimeQuote,
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

        # Update only allowed fields; category_id and description allow None to clear
        allowed_fields = {"name", "description", "category_id"}
        nullable_fields = {"category_id", "description"}
        for field, value in kwargs.items():
            if field not in allowed_fields:
                continue
            if field in nullable_fields or value is not None:
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

    def get_quotes(self, watchlist_id: int, user_id: int) -> Optional[list[QuoteResponse]]:
        """Get price quotes for all symbols in a watchlist.

        Uses cache first (30s TTL), falls back to database queries.
        Batch queries — no per-symbol round-trips.

        Returns:
            List of QuoteResponse in watchlist priority order,
            None if watchlist not found or not owned by user.
            Symbols with no data in either table are excluded.
        """
        watchlist = self.get_watchlist(watchlist_id, user_id)
        if not watchlist:
            return None

        symbol_rows = self.get_watchlist_symbols(watchlist_id, user_id)
        if not symbol_rows:
            return []

        symbols = [ws.stock.symbol for ws in symbol_rows]

        # Try cache first
        from src.api.schedule.manager import get_quote_cache_service

        cache_service = get_quote_cache_service()
        cached = cache_service.get_quotes(symbols)

        if len(cached) == len(symbols):
            # Prices from cache; always fetch intraday from DB for sparklines
            stock_ids = [int(ws.stock_id) for ws in symbol_rows]
            intraday_by_stock = self._fetch_intraday_by_stock_ids(stock_ids)
            symbol_to_stock_id = {ws.stock.symbol: int(ws.stock_id) for ws in symbol_rows}
            symbol_to_quote = {q.symbol: q for q in cached}
            result = []
            for symbol in symbols:
                q = symbol_to_quote[symbol]
                intraday_data = intraday_by_stock.get(symbol_to_stock_id[symbol], [])
                result.append(
                    QuoteResponse(
                        symbol=q.symbol,
                        last=q.last,
                        low=q.low,
                        high=q.high,
                        change=q.change,
                        change_pct=q.change_pct,
                        source=q.source,
                        date=q.date,
                        intraday=intraday_data,
                    )
                )
            return result

        # Cache miss: fall back to database queries
        return self._get_quotes_from_db(symbol_rows)

    def _get_quotes_from_db(
        self,
        symbol_rows: List[WatchlistSymbol],
    ) -> list[QuoteResponse]:
        """Get quotes from database (realtime + EOD fallback).

        Args:
            symbol_rows: List of WatchlistSymbol objects

        Returns:
            List of QuoteResponse objects
        """
        stock_ids = [int(ws.stock_id) for ws in symbol_rows]
        stock_id_to_symbol: dict[int, str] = {
            int(ws.stock_id): ws.stock.symbol for ws in symbol_rows
        }

        # Batch 1: realtime quotes (today only, latest per stock)
        rq_rn = (
            func.row_number()
            .over(
                partition_by=RealtimeQuote.stock_id,
                order_by=RealtimeQuote.timestamp.desc(),
            )
            .label("rn")
        )
        rq_subq = (
            select(
                RealtimeQuote.stock_id,
                RealtimeQuote.last,
                RealtimeQuote.low,
                RealtimeQuote.high,
                RealtimeQuote.change,
                RealtimeQuote.change_pct,
                rq_rn,
            )
            .where(
                RealtimeQuote.stock_id.in_(stock_ids),
                func.date(RealtimeQuote.timestamp) == date.today(),
            )
            .subquery()
        )
        realtime_rows = self.db_session.execute(select(rq_subq).where(rq_subq.c.rn == 1)).all()

        covered_ids: set[int] = {int(row.stock_id) for row in realtime_rows}
        missing_ids: list[int] = [sid for sid in stock_ids if sid not in covered_ids]

        intraday_by_stock = self._fetch_intraday_by_stock_ids(list(covered_ids))

        result: dict[int, QuoteResponse] = {}
        for row in realtime_rows:
            intraday_data = intraday_by_stock.get(int(row.stock_id), [])
            result[int(row.stock_id)] = QuoteResponse(
                symbol=stock_id_to_symbol[int(row.stock_id)],
                last=float(row.last) if row.last is not None else None,
                low=float(row.low) if row.low is not None else None,
                high=float(row.high) if row.high is not None else None,
                change=float(row.change) if row.change is not None else None,
                change_pct=float(row.change_pct) if row.change_pct is not None else None,
                source="realtime",
                intraday=intraday_data,
            )

        # Batch 2: EOD fallback (latest 2 candles per missing stock)
        if missing_ids:
            dc_rn = (
                func.row_number()
                .over(
                    partition_by=DailyCandle.stock_id,
                    order_by=DailyCandle.timestamp.desc(),
                )
                .label("rn")
            )
            dc_subq = (
                select(
                    DailyCandle.stock_id,
                    DailyCandle.close,
                    DailyCandle.low,
                    DailyCandle.high,
                    DailyCandle.timestamp,
                    dc_rn,
                )
                .where(DailyCandle.stock_id.in_(missing_ids))
                .subquery()
            )
            eod_rows = self.db_session.execute(
                select(dc_subq).where(dc_subq.c.rn <= 2).order_by(dc_subq.c.stock_id, dc_subq.c.rn)
            ).all()

            candles_by_stock: dict[int, list] = defaultdict(list)
            for row in eod_rows:
                candles_by_stock[int(row.stock_id)].append(row)

            for stock_id, candles in candles_by_stock.items():
                latest_close = float(candles[0].close) if candles[0].close is not None else None
                candle_low = float(candles[0].low) if candles[0].low is not None else None
                candle_high = float(candles[0].high) if candles[0].high is not None else None

                if (
                    len(candles) >= 2
                    and candles[0].close is not None
                    and candles[1].close is not None
                ):
                    change = float(candles[0].close - candles[1].close)
                    prev = float(candles[1].close)
                    change_pct = (change / prev * 100) if prev != 0 else None
                else:
                    change = None
                    change_pct = None

                result[stock_id] = QuoteResponse(
                    symbol=stock_id_to_symbol[stock_id],
                    last=latest_close,
                    low=candle_low,
                    high=candle_high,
                    change=change,
                    change_pct=change_pct,
                    source="eod",
                    date=(
                        candles[0].timestamp.strftime("%Y-%m-%d") if candles[0].timestamp else None
                    ),
                    intraday=[],  # No intraday for EOD
                )

        return [result[int(ws.stock_id)] for ws in symbol_rows if int(ws.stock_id) in result]

    def _fetch_intraday_by_stock_ids(self, stock_ids: list[int]) -> dict[int, List[IntradayPoint]]:
        """Fetch today's intraday close prices for multiple stocks (batch).

        Returns a dict of stock_id → list of IntradayPoint (max 30 per stock).
        """
        if not stock_ids:
            return {}

        rows = (
            self.db_session.query(
                IntradayCandle.stock_id,
                IntradayCandle.timestamp,
                IntradayCandle.close,
            )
            .filter(
                IntradayCandle.stock_id.in_(stock_ids),
                func.date(IntradayCandle.timestamp) == date.today(),
            )
            .order_by(IntradayCandle.timestamp.asc())
            .all()
        )

        intraday_by_stock: dict[int, List[IntradayPoint]] = defaultdict(list)
        counter: dict[int, int] = defaultdict(int)
        for candle in rows:
            sid = int(candle.stock_id)
            if counter[sid] < 30 and candle.close is not None:
                intraday_by_stock[sid].append(
                    IntradayPoint(time=candle.timestamp.isoformat(), close=float(candle.close))
                )
                counter[sid] += 1

        return dict(intraday_by_stock)

    def _get_intraday_points(self, stock_id: int) -> List[IntradayPoint]:
        """Get intraday close prices for sparkline rendering.

        Fetches the last 30 intraday candles (1h resolution) for today.
        Returns list of IntradayPoint objects ordered by time ascending.

        Args:
            stock_id: ID of the stock

        Returns:
            List of IntradayPoint objects, empty if no intraday data
        """
        candles = (
            self.db_session.query(
                IntradayCandle.timestamp,
                IntradayCandle.close,
            )
            .filter(
                IntradayCandle.stock_id == stock_id,
                func.date(IntradayCandle.timestamp) == date.today(),
            )
            .order_by(IntradayCandle.timestamp.asc())
            .limit(30)
            .all()
        )

        return [
            IntradayPoint(
                time=candle.timestamp.isoformat(),
                close=float(candle.close),
            )
            for candle in candles
            if candle.close is not None
        ]

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

    def get_watchlists_grouped(self, user_id: int) -> List[CategoryWatchlists]:
        """Get watchlists grouped by category with symbol counts.

        Args:
            user_id: ID of the user

        Returns:
            List of CategoryWatchlists objects with category and watchlists.
            Ordered by category sort_order.
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

            # Build watchlist summaries with symbol counts
            watchlist_summaries = []
            for watchlist in watchlists:
                # Count symbols in this watchlist
                symbol_count = (
                    self.db_session.query(WatchlistSymbol)
                    .filter(WatchlistSymbol.watchlist_id == watchlist.id)
                    .count()
                )

                watchlist_summaries.append(
                    WatchlistSummary(
                        id=int(watchlist.id),
                        name=str(watchlist.name),
                        category_id=(
                            int(watchlist.category_id)
                            if watchlist.category_id is not None
                            else None
                        ),
                        description=(
                            str(watchlist.description)
                            if watchlist.description is not None
                            else None
                        ),
                        is_auto_generated=bool(watchlist.is_auto_generated),
                        scanner_name=(
                            str(watchlist.scanner_name)
                            if watchlist.scanner_name is not None
                            else None
                        ),
                        watchlist_mode=str(watchlist.watchlist_mode),
                        source_scan_date=watchlist.source_scan_date,  # type: ignore[arg-type]
                        created_at=watchlist.created_at,  # type: ignore[arg-type]
                        updated_at=watchlist.updated_at,  # type: ignore[arg-type]
                        symbol_count=symbol_count,
                    )
                )

            # Add category with its watchlists
            result.append(
                CategoryWatchlists(
                    category=CategoryResponse.model_validate(category),
                    watchlists=watchlist_summaries,
                )
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
            uncategorized_summaries = []
            for watchlist in uncategorized_watchlists:
                symbol_count = (
                    self.db_session.query(WatchlistSymbol)
                    .filter(WatchlistSymbol.watchlist_id == watchlist.id)
                    .count()
                )
                uncategorized_summaries.append(
                    WatchlistSummary(
                        id=int(watchlist.id),
                        name=str(watchlist.name),
                        category_id=(
                            int(watchlist.category_id)
                            if watchlist.category_id is not None
                            else None
                        ),
                        description=(
                            str(watchlist.description)
                            if watchlist.description is not None
                            else None
                        ),
                        is_auto_generated=bool(watchlist.is_auto_generated),
                        scanner_name=(
                            str(watchlist.scanner_name)
                            if watchlist.scanner_name is not None
                            else None
                        ),
                        watchlist_mode=str(watchlist.watchlist_mode),
                        source_scan_date=watchlist.source_scan_date,  # type: ignore[arg-type]
                        created_at=watchlist.created_at,  # type: ignore[arg-type]
                        updated_at=watchlist.updated_at,  # type: ignore[arg-type]
                        symbol_count=symbol_count,
                    )
                )

            # Create synthetic category for uncategorized watchlists
            result.append(
                CategoryWatchlists(
                    category=CategoryResponse(
                        id=0,  # Synthetic ID
                        name="Uncategorized",
                        description=None,
                        color=None,
                        icon=None,
                        is_system=False,
                        sort_order=999,  # Always last
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    ),
                    watchlists=uncategorized_summaries,
                )
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

        # Deduplicate results by stock_id, keeping the most recent match for each stock
        # This handles multiple scans per day (pre-close, EOD, etc.)
        seen_stocks = {}
        for result in results:
            if result.stock_id not in seen_stocks:
                seen_stocks[result.stock_id] = result
            elif result.matched_at > seen_stocks[result.stock_id].matched_at:
                seen_stocks[result.stock_id] = result
        results = list(seen_stocks.values())

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
            ).delete(synchronize_session=False)
            self.db.flush()  # Ensure delete is committed before adding new symbols
            # Update the source_scan_date to reflect the new scan
            existing.source_scan_date = datetime.combine(scan_date, datetime.min.time())  # type: ignore[assignment]
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
                source_scan_date=datetime.combine(scan_date, datetime.min.time()),
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
            try:
                self.db.flush()
            except IntegrityError:
                # Concurrent process already inserted — roll back and re-fetch
                self.db.rollback()
                watchlist = (
                    self.db.query(Watchlist)
                    .filter(Watchlist.user_id == user_id)
                    .filter(Watchlist.name == watchlist_name)
                    .filter(Watchlist.scanner_name == scanner_name)
                    .filter(Watchlist.watchlist_mode == mode)
                    .first()
                )

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
