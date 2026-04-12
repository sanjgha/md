"""API routes for watchlist CRUD operations.

This module provides endpoints for:
- GET /api/watchlists - List all watchlists grouped by category
- POST /api/watchlists - Create new watchlist
- GET /api/watchlists/{id} - Get watchlist details with symbols
- PUT /api/watchlists/{id} - Update watchlist
- DELETE /api/watchlists/{id} - Delete watchlist
- GET /api/watchlists/categories - List categories
- POST /api/watchlists/categories - Create category
- DELETE /api/watchlists/categories/{id} - Delete category (system protected)
- POST /api/watchlists/{id}/clone - Clone watchlist with symbols
- GET /api/watchlists/{id}/symbols - List symbols in a watchlist
- POST /api/watchlists/{id}/symbols - Add symbol to watchlist
- DELETE /api/watchlists/{id}/symbols/{symbol} - Remove symbol from watchlist
"""

from typing import List, cast

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from src.api.deps import get_current_user, get_db
from src.api.watchlists.schemas import (
    CategoryCreate,
    CategoryResponse,
    WatchlistCloneRequest,
    WatchlistCreate,
    WatchlistResponse,
    WatchlistSymbolAddRequest,
    WatchlistSymbolAddResponse,
    WatchlistSymbolDetailResponse,
    WatchlistSymbolRemoveResponse,
    WatchlistSymbolsResponse,
    WatchlistUpdate,
)
from src.api.watchlists.service import WatchlistService
from src.db.models import User
from src.db.models import WatchlistCategory

router = APIRouter()


def _get_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Resolve authenticated user from request.state.user_id."""
    return get_current_user(request, db)


# ========== Watchlist CRUD Endpoints ==========


@router.get("", response_model=List[dict])
def list_watchlists(
    user: User = Depends(_get_user),
    db: Session = Depends(get_db),
):
    """Get all watchlists for the current user, grouped by category.

    Returns a list of categories with their watchlists and symbol counts.
    """
    service = WatchlistService(db)
    return service.get_watchlists_grouped(cast(int, user.id))


@router.post("", response_model=WatchlistResponse, status_code=201)
def create_watchlist(
    payload: WatchlistCreate,
    user: User = Depends(_get_user),
    db: Session = Depends(get_db),
):
    """Create a new watchlist for the current user.

    Validates that category_id (if provided) belongs to the user.
    """
    # Validate category ownership if provided
    if payload.category_id is not None:
        category = db.get(WatchlistCategory, payload.category_id)
        if not category or category.user_id != user.id:
            raise HTTPException(
                status_code=400,
                detail="Invalid category_id",
            )

    service = WatchlistService(db)
    watchlist = service.create_watchlist(
        user_id=cast(int, user.id),
        name=payload.name,
        description=payload.description,
        category_id=payload.category_id,
    )
    return watchlist


@router.get("/categories", response_model=list[CategoryResponse])
def get_categories(
    user: User = Depends(_get_user),
    db: Session = Depends(get_db),
):
    """Get all categories for the authenticated user, ordered by sort_order."""
    from src.api.watchlists.service import WatchlistService

    service = WatchlistService(db)
    categories = service.get_user_categories(cast(int, user.id))
    return categories


@router.post("/categories", response_model=CategoryResponse, status_code=201)
def create_category(
    category_data: CategoryCreate,
    user: User = Depends(_get_user),
    db: Session = Depends(get_db),
):
    """Create a new category for the authenticated user.

    Args:
        category_data: Category creation schema with name, optional description, color, icon

    Returns:
        Created category

    Raises:
        400: If category name already exists for this user
    """
    from src.api.watchlists.service import WatchlistService

    service = WatchlistService(db)

    # Check for duplicate category name
    existing_categories = service.get_user_categories(cast(int, user.id))
    if any(cat.name == category_data.name for cat in existing_categories):
        raise HTTPException(
            status_code=400,
            detail=f"Category '{category_data.name}' already exists",
        )

    # Create category (user-created categories are never system categories)
    category = service.create_category(
        user_id=cast(int, user.id),
        name=category_data.name,
        icon=category_data.icon if category_data.icon is not None else "",
        is_system=False,
        description=category_data.description,
        color=category_data.color,
    )

    return category


@router.delete("/categories/{category_id}", status_code=200)
def delete_category(
    category_id: int,
    user: User = Depends(_get_user),
    db: Session = Depends(get_db),
):
    """Delete a category by ID.

    System categories (is_system=True) are protected and cannot be deleted.

    Args:
        category_id: ID of the category to delete

    Raises:
        403: If attempting to delete a system category
        404: If category not found or not owned by user
    """
    # Get category and verify ownership
    category = (
        db.query(WatchlistCategory)
        .filter(
            WatchlistCategory.id == category_id,
            WatchlistCategory.user_id == user.id,
        )
        .first()
    )

    if not category:
        raise HTTPException(
            status_code=404,
            detail=f"Category with ID {category_id} not found",
        )

    # Protect system categories
    if category.is_system:
        raise HTTPException(
            status_code=403,
            detail="Cannot delete system categories",
        )

    # Delete the category
    db.delete(category)
    db.commit()

    return {"message": "Category deleted successfully"}


@router.get("/{watchlist_id}", response_model=WatchlistResponse)
def get_watchlist(
    watchlist_id: int,
    user: User = Depends(_get_user),
    db: Session = Depends(get_db),
):
    """Get a specific watchlist with its symbols.

    Returns 404 if watchlist doesn't exist or isn't owned by the user.
    """
    service = WatchlistService(db)
    watchlist = service.get_watchlist(watchlist_id, cast(int, user.id))

    if not watchlist:
        raise HTTPException(
            status_code=404,
            detail="Watchlist not found",
        )

    return watchlist


@router.put("/{watchlist_id}", response_model=WatchlistResponse)
def update_watchlist(
    watchlist_id: int,
    payload: WatchlistUpdate,
    user: User = Depends(_get_user),
    db: Session = Depends(get_db),
):
    """Update a watchlist.

    Only updates fields that are provided (partial update).
    Validates category ownership if category_id is being updated.
    Returns 404 if watchlist doesn't exist or isn't owned by the user.
    """
    # Validate category ownership if provided
    if payload.category_id is not None:
        category = db.get(WatchlistCategory, payload.category_id)
        if not category or category.user_id != user.id:
            raise HTTPException(
                status_code=400,
                detail="Invalid category_id",
            )

    service = WatchlistService(db)

    # Build update kwargs from non-None fields
    update_data = payload.model_dump(exclude_none=True)

    watchlist = service.update_watchlist(
        watchlist_id=watchlist_id,
        user_id=cast(int, user.id),
        **update_data,
    )

    if not watchlist:
        raise HTTPException(
            status_code=404,
            detail="Watchlist not found",
        )

    return watchlist


@router.delete("/{watchlist_id}", status_code=204)
def delete_watchlist(
    watchlist_id: int,
    user: User = Depends(_get_user),
    db: Session = Depends(get_db),
):
    """Delete a watchlist.

    Returns 204 on success, 404 if watchlist doesn't exist or isn't owned by the user.
    """
    service = WatchlistService(db)
    success = service.delete_watchlist(watchlist_id, cast(int, user.id))

    if not success:
        raise HTTPException(
            status_code=404,
            detail="Watchlist not found",
        )

    return Response(status_code=204)


# ========== Symbol Management Endpoints ==========


@router.get("/{watchlist_id}/symbols", response_model=WatchlistSymbolsResponse)
def list_symbols(
    watchlist_id: int,
    user: User = Depends(_get_user),
    db: Session = Depends(get_db),
):
    """Get all symbols in a watchlist with stock details.

    Returns 404 if watchlist doesn't exist or isn't owned by the user.
    """
    service = WatchlistService(db)

    # Verify watchlist ownership
    watchlist = service.get_watchlist(watchlist_id, cast(int, user.id))
    if not watchlist:
        raise HTTPException(
            status_code=404,
            detail="Watchlist not found",
        )

    # Get symbols with stock information
    symbols = service.get_watchlist_symbols(watchlist_id, cast(int, user.id))

    # Build response with stock details
    symbol_details = []
    for ws in symbols:
        symbol_details.append(
            WatchlistSymbolDetailResponse(
                id=cast(int, ws.id),
                stock_id=cast(int, ws.stock_id),
                symbol=ws.stock.symbol,
                name=ws.stock.name,
                notes=cast(str | None, ws.notes),
                priority=cast(int, ws.priority),
                added_at=cast(datetime, ws.added_at),
            )
        )

    return WatchlistSymbolsResponse(symbols=symbol_details)


@router.post("/{watchlist_id}/symbols", response_model=WatchlistSymbolAddResponse, status_code=201)
def add_symbol(
    watchlist_id: int,
    payload: WatchlistSymbolAddRequest,
    user: User = Depends(_get_user),
    db: Session = Depends(get_db),
):
    """Add a symbol to a watchlist.

    Args:
        watchlist_id: ID of the watchlist
        payload: Request body with symbol (required) and notes (optional)

    Returns:
        Created symbol with stock details

    Raises:
        404: If watchlist not found or stock symbol doesn't exist
        400: If symbol already exists in the watchlist
    """
    service = WatchlistService(db)

    # Normalize symbol to uppercase
    symbol = payload.symbol.upper().strip()

    # Add symbol using service
    watchlist_symbol = service.add_symbol(
        watchlist_id=watchlist_id,
        user_id=cast(int, user.id),
        symbol=symbol,
        notes=payload.notes,
    )

    # Handle errors
    if not watchlist_symbol:
        # Check if watchlist exists
        watchlist = service.get_watchlist(watchlist_id, cast(int, user.id))
        if not watchlist:
            raise HTTPException(
                status_code=404,
                detail="Watchlist not found",
            )

        # Watchlist exists, so either stock doesn't exist or symbol is duplicate
        # Check if stock exists
        from src.db.models import Stock

        stock = db.query(Stock).filter(Stock.symbol == symbol).first()
        if not stock:
            raise HTTPException(
                status_code=404,
                detail=f"Stock symbol '{symbol}' not found",
            )

        # Stock exists, so it must be a duplicate
        raise HTTPException(
            status_code=400,
            detail=f"Symbol '{symbol}' already exists in this watchlist",
        )

    # Build response with stock details
    symbol_detail = WatchlistSymbolDetailResponse(
        id=cast(int, watchlist_symbol.id),
        stock_id=cast(int, watchlist_symbol.stock_id),
        symbol=watchlist_symbol.stock.symbol,
        name=watchlist_symbol.stock.name,
        notes=cast(str | None, watchlist_symbol.notes),
        priority=cast(int, watchlist_symbol.priority),
        added_at=cast(datetime, watchlist_symbol.added_at),
    )

    return WatchlistSymbolAddResponse(
        message=f"Symbol '{symbol}' added to watchlist",
        symbol=symbol_detail,
    )


@router.delete("/{watchlist_id}/symbols/{symbol}", response_model=WatchlistSymbolRemoveResponse)
def remove_symbol(
    watchlist_id: int,
    symbol: str,
    user: User = Depends(_get_user),
    db: Session = Depends(get_db),
):
    """Remove a symbol from a watchlist.

    Args:
        watchlist_id: ID of the watchlist
        symbol: Stock symbol to remove (case-insensitive)

    Returns:
        Success message

    Raises:
        404: If watchlist not found, stock doesn't exist, or symbol not in watchlist
    """
    service = WatchlistService(db)

    # Normalize symbol to uppercase
    symbol = symbol.upper().strip()

    # Remove symbol using service
    success = service.remove_symbol(
        watchlist_id=watchlist_id,
        user_id=cast(int, user.id),
        symbol=symbol,
    )

    # Handle errors
    if not success:
        # Check if watchlist exists
        watchlist = service.get_watchlist(watchlist_id, cast(int, user.id))
        if not watchlist:
            raise HTTPException(
                status_code=404,
                detail="Watchlist not found",
            )

        # Watchlist exists, so either stock doesn't exist or symbol not in watchlist
        # Check if stock exists
        from src.db.models import Stock

        stock = db.query(Stock).filter(Stock.symbol == symbol).first()
        if not stock:
            raise HTTPException(
                status_code=404,
                detail=f"Stock symbol '{symbol}' not found",
            )

        # Stock exists but not in watchlist
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol}' not found in this watchlist",
        )

    return WatchlistSymbolRemoveResponse(
        message=f"Symbol '{symbol}' removed from watchlist",
    )


# ========== Category Endpoints ==========


# ========== Watchlist Clone Endpoint ==========


@router.post("/{watchlist_id}/clone", response_model=WatchlistResponse, status_code=201)
def clone_watchlist(
    watchlist_id: int,
    clone_data: WatchlistCloneRequest,
    user: User = Depends(_get_user),
    db: Session = Depends(get_db),
):
    """Clone a watchlist with all its symbols.

    The cloned watchlist:
    - Gets a new unique ID
    - Uses the provided name (must be unique for the user)
    - Copies all symbols from the original watchlist
    - Can optionally override category_id and description
    - Is never marked as auto-generated (is_auto_generated=False)

    Args:
        watchlist_id: ID of the watchlist to clone
        clone_data: Clone request with required name and optional category_id, description

    Returns:
        Cloned watchlist with all symbols

    Raises:
        400: If watchlist with the same name already exists for this user
        404: If watchlist not found or not owned by user
    """
    from src.api.watchlists.service import WatchlistService

    service = WatchlistService(db)

    # Verify watchlist exists and is owned by user
    original_watchlist = service.get_watchlist(watchlist_id, cast(int, user.id))
    if not original_watchlist:
        raise HTTPException(
            status_code=404,
            detail=f"Watchlist with ID {watchlist_id} not found",
        )

    # Check for duplicate name
    existing_watchlists = service.get_user_watchlists(cast(int, user.id))
    if any(wl.name == clone_data.name for wl in existing_watchlists):
        raise HTTPException(
            status_code=400,
            detail=f"Watchlist '{clone_data.name}' already exists",
        )

    # Clone the watchlist
    cloned_watchlist = service.clone_watchlist(
        watchlist_id=watchlist_id,
        user_id=cast(int, user.id),
        new_name=clone_data.name,
    )

    if not cloned_watchlist:
        raise HTTPException(
            status_code=500,
            detail="Failed to clone watchlist",
        )

    # Apply optional overrides
    if clone_data.category_id is not None:
        cloned_watchlist.category_id = clone_data.category_id  # type: ignore[assignment]
    if clone_data.description is not None:
        cloned_watchlist.description = clone_data.description  # type: ignore[assignment]

    db.commit()
    db.refresh(cloned_watchlist)

    # Load symbols for response
    symbols = service.get_watchlist_symbols(cast(int, cloned_watchlist.id), cast(int, user.id))

    # Build response with symbols
    from src.api.watchlists.schemas import WatchlistSymbolResponse

    response_data = WatchlistResponse.model_validate(cloned_watchlist)
    response_data.symbols = [WatchlistSymbolResponse.model_validate(sym) for sym in symbols]

    return response_data
