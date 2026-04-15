"""Pydantic schemas for watchlists API."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class WatchlistSymbolCreate(BaseModel):
    """Schema for creating a watchlist symbol."""

    stock_id: int = Field(..., description="ID of the stock to add to watchlist")
    notes: Optional[str] = Field(None, description="Optional notes about the symbol")
    priority: int = Field(default=0, description="Priority for ordering (default: 0)")


class WatchlistCreate(BaseModel):
    """Schema for creating a watchlist."""

    name: str = Field(..., min_length=1, max_length=100, description="Watchlist name")
    category_id: Optional[int] = Field(None, description="Optional category ID")
    description: Optional[str] = Field(None, description="Optional description")


class WatchlistUpdate(BaseModel):
    """Schema for updating a watchlist."""

    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Watchlist name")
    category_id: Optional[int] = Field(None, description="Optional category ID")
    description: Optional[str] = Field(None, description="Optional description")


class WatchlistSymbolResponse(BaseModel):
    """Schema for watchlist symbol response."""

    id: int
    stock_id: int
    notes: Optional[str]
    priority: int
    added_at: datetime

    model_config = {"from_attributes": True}


class WatchlistResponse(BaseModel):
    """Schema for watchlist response."""

    id: int
    name: str
    category_id: Optional[int]
    description: Optional[str]
    is_auto_generated: bool
    scanner_name: Optional[str]
    watchlist_mode: str
    source_scan_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    symbols: List[WatchlistSymbolResponse] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class CategoryCreate(BaseModel):
    """Schema for creating a watchlist category."""

    name: str = Field(..., min_length=1, max_length=100, description="Category name")
    description: Optional[str] = Field(None, description="Optional description")
    color: Optional[str] = Field(None, max_length=7, description="Hex color code (e.g., #FF5733)")
    icon: Optional[str] = Field(None, max_length=50, description="Icon name")


class CategoryUpdate(BaseModel):
    """Schema for updating a watchlist category."""

    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Category name")
    description: Optional[str] = Field(None, description="Optional description")
    color: Optional[str] = Field(None, max_length=7, description="Hex color code (e.g., #FF5733)")
    icon: Optional[str] = Field(None, max_length=50, description="Icon name")


class CategoryResponse(BaseModel):
    """Schema for category response."""

    id: int
    name: str
    description: Optional[str]
    color: Optional[str]
    icon: Optional[str]
    is_system: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WatchlistListResponse(BaseModel):
    """Schema for paginated watchlist list response."""

    total: int = Field(..., description="Total number of watchlists")
    items: List[WatchlistResponse] = Field(..., description="List of watchlists")


class WatchlistSummary(BaseModel):
    """Schema for watchlist summary in grouped view."""

    id: int
    name: str
    category_id: Optional[int]
    description: Optional[str]
    is_auto_generated: bool
    scanner_name: Optional[str]
    watchlist_mode: str
    source_scan_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    symbol_count: int = Field(..., description="Number of symbols in watchlist")

    model_config = {"from_attributes": True}


class CategoryWatchlists(BaseModel):
    """Schema for category with its watchlists."""

    category: CategoryResponse
    watchlists: List[WatchlistSummary]


class WatchlistCloneRequest(BaseModel):
    """Schema for cloning a watchlist."""

    name: str = Field(
        ..., min_length=1, max_length=100, description="Name for the cloned watchlist"
    )
    category_id: Optional[int] = Field(None, description="Optional category ID for the clone")
    description: Optional[str] = Field(None, description="Optional description for the clone")


class WatchlistSymbolAddRequest(BaseModel):
    """Schema for adding a symbol to a watchlist."""

    symbol: str = Field(..., min_length=1, max_length=10, description="Stock symbol to add")
    notes: Optional[str] = Field(None, description="Optional notes about the symbol")


class WatchlistSymbolDetailResponse(BaseModel):
    """Schema for watchlist symbol with stock details."""

    id: int
    stock_id: int
    symbol: str
    name: Optional[str]
    notes: Optional[str]
    priority: int
    added_at: datetime

    model_config = {"from_attributes": True}


class WatchlistSymbolsResponse(BaseModel):
    """Schema for watchlist symbols list response."""

    symbols: List[WatchlistSymbolDetailResponse] = Field(default_factory=list)


class WatchlistSymbolAddResponse(BaseModel):
    """Schema for successful symbol addition response."""

    message: str
    symbol: WatchlistSymbolDetailResponse


class WatchlistSymbolRemoveResponse(BaseModel):
    """Schema for successful symbol removal response."""

    message: str
