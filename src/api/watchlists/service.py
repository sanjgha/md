"""Watchlist service layer with business logic for CRUD operations."""

from typing import List, Optional

from sqlalchemy.orm import Session

from src.db.models import Watchlist


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

        # Update only allowed fields
        allowed_fields = {"name", "description", "category_id"}
        for field, value in kwargs.items():
            if field in allowed_fields and value is not None:
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
