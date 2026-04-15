/**
 * Watchlists API client.
 * Provides methods for watchlist CRUD, symbol management, categories, and cloning.
 */

import { apiFetch } from "./api";
import type {
  Watchlist,
  WatchlistCreate,
  Category,
  CategoryCreate,
  WatchlistUpdate,
  CategoryWatchlists,
} from "../pages/watchlists/types";

/**
 * Watchlists API client object with nested methods
 */
export const watchlistsAPI = {
  /**
   * List all watchlists grouped by category
   */
  list: (): Promise<CategoryWatchlists[]> =>
    apiFetch("/api/watchlists"),

  /**
   * Create a new watchlist
   */
  create: (data: WatchlistCreate): Promise<Watchlist> =>
    apiFetch("/api/watchlists", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  /**
   * Get a single watchlist by ID
   */
  get: (id: number): Promise<Watchlist> =>
    apiFetch(`/api/watchlists/${id}`),

  /**
   * Update a watchlist
   */
  update: (id: number, data: Partial<WatchlistUpdate>): Promise<Watchlist> =>
    apiFetch(`/api/watchlists/${id}`, {
      method: "PUT",
      body: JSON.stringify(data),
    }),

  /**
   * Delete a watchlist
   */
  delete: (id: number): Promise<void> =>
    apiFetch(`/api/watchlists/${id}`, {
      method: "DELETE",
    }),

  /**
   * Symbol management methods
   */
  symbols: {
    /**
     * List symbols in a watchlist
     */
    list: (watchlistId: number): Promise<WatchlistSymbol[]> =>
      apiFetch(`/api/watchlists/${watchlistId}/symbols`),

    /**
     * Add a symbol to a watchlist
     */
    add: (
      watchlistId: number,
      symbol: string,
      notes?: string
    ): Promise<{ success: boolean }> =>
      apiFetch(`/api/watchlists/${watchlistId}/symbols`, {
        method: "POST",
        body: JSON.stringify({ symbol, notes }),
      }),

    /**
     * Remove a symbol from a watchlist
     */
    remove: (watchlistId: number, symbol: string): Promise<{ success: boolean }> =>
      apiFetch(`/api/watchlists/${watchlistId}/symbols/${symbol}`, {
        method: "DELETE",
      }),
  },

  /**
   * Category management methods
   */
  categories: {
    /**
     * List all categories
     */
    list: (): Promise<Category[]> =>
      apiFetch("/api/watchlists/categories"),

    /**
     * Create a new category
     */
    create: (data: CategoryCreate): Promise<Category> =>
      apiFetch("/api/watchlists/categories", {
        method: "POST",
        body: JSON.stringify(data),
      }),
  },

  /**
   * Clone a watchlist
   */
  clone: (id: number, data: { name: string }): Promise<Watchlist> =>
    apiFetch(`/api/watchlists/${id}/clone`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
};
