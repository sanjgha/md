/**
 * TypeScript interfaces for Watchlists API.
 * Matches Pydantic schemas in src/api/watchlists/schemas.py
 */

/**
 * Watchlist symbol response
 */
export interface WatchlistSymbol {
  id: number;
  stock_id: number;
  symbol: string;
  name: string | null;
  notes: string | null;
  priority: number;
  added_at: string; // ISO datetime
}

/**
 * Watchlist summary (for grouped view)
 */
export interface WatchlistSummary {
  id: number;
  name: string;
  category_id: number | null;
  description: string | null;
  is_auto_generated: boolean;
  scanner_name: string | null;
  watchlist_mode: string;
  source_scan_date: string | null; // ISO datetime
  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime
  symbol_count: number;
}

/**
 * Watchlist response (full detail with symbols)
 */
export interface Watchlist {
  id: number;
  name: string;
  category_id: number | null;
  description: string | null;
  is_auto_generated: boolean;
  scanner_name: string | null;
  watchlist_mode: string;
  source_scan_date: string | null; // ISO datetime
  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime
  symbols: WatchlistSymbol[];
  symbol_count?: number;
}

/**
 * Watchlist creation request
 */
export interface WatchlistCreate {
  name: string;
  category_id?: number | null;
  description?: string | null;
}

/**
 * Watchlist update request
 */
export interface WatchlistUpdate {
  name?: string;
  category_id?: number | null;
  description?: string | null;
}

/**
 * Category response
 */
export interface Category {
  id: number;
  name: string;
  description: string | null;
  color: string | null;
  icon: string | null;
  is_system: boolean;
  sort_order: number;
  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime
}

/**
 * Category creation request
 */
export interface CategoryCreate {
  name: string;
  description?: string | null;
  color?: string | null;
  icon?: string | null;
}

/**
 * Category with its watchlists
 */
export interface CategoryWatchlists {
  category: Category;
  watchlists: WatchlistSummary[];
}

/**
 * Paginated watchlist list response
 */
export interface WatchlistListResponse {
  total: number;
  items: Watchlist[];
}

/**
 * Watchlist clone request
 */
export interface WatchlistCloneRequest {
  name: string;
  category_id?: number | null;
  description?: string | null;
}

/**
 * Add symbol to watchlist request
 */
export interface WatchlistSymbolAddRequest {
  symbol: string;
  notes?: string | null;
}

/**
 * Watchlist symbols list response
 */
export interface WatchlistSymbolsResponse {
  symbols: WatchlistSymbol[];
}

/**
 * Symbol addition response
 */
export interface WatchlistSymbolAddResponse {
  message: string;
  symbol: WatchlistSymbol;
}

/**
 * Symbol removal response
 */
export interface WatchlistSymbolRemoveResponse {
  message: string;
}

/**
 * Quote response for a symbol
 */
export interface QuoteResponse {
  symbol: string;
  last: number | null;
  change: number | null;
  change_pct: number | null;
  source: "realtime" | "eod";
  date: string | null;  // ISO date string (YYYY-MM-DD) for EOD quotes, null for realtime
}

/**
 * Symbol reference for keyboard navigation
 */
export interface WatchlistSymbolRef {
  symbol: string;
  onRemove: () => void;
}
