/**
 * Watchlists API client.
 * Provides methods for watchlist CRUD, symbol management, categories, and cloning.
 */

import { apiGet, apiPost, apiPut } from "./api";
import type {
  Watchlist,
  WatchlistCreate,
  WatchlistListResponse,
  WatchlistSymbolAddRequest,
  WatchlistSymbolAddResponse,
  WatchlistSymbolRemoveResponse,
  WatchlistSymbolsResponse,
  Category,
  CategoryCreate,
  CategoryWatchlists,
  WatchlistCloneRequest,
  WatchlistUpdate,
} from "../pages/watchlists/types";

const BASE_URL = "/api/watchlists";

/**
 * List all watchlists with optional pagination
 */
export async function listWatchlists(skip = 0, limit = 100): Promise<WatchlistListResponse> {
  return apiGet<WatchlistListResponse>(`${BASE_URL}?skip=${skip}&limit=${limit}`);
}

/**
 * Get watchlists grouped by category
 */
export async function listWatchlistsGrouped(): Promise<CategoryWatchlists[]> {
  return apiGet<CategoryWatchlists[]>(`${BASE_URL}/grouped`);
}

/**
 * Create a new watchlist
 */
export async function createWatchlist(data: WatchlistCreate): Promise<Watchlist> {
  return apiPost<Watchlist>(BASE_URL, data);
}

/**
 * Get a single watchlist by ID
 */
export async function getWatchlist(id: number): Promise<Watchlist> {
  return apiGet<Watchlist>(`${BASE_URL}/${id}`);
}

/**
 * Update a watchlist
 */
export async function updateWatchlist(id: number, data: WatchlistUpdate): Promise<Watchlist> {
  return apiPut<Watchlist>(`${BASE_URL}/${id}`, data);
}

/**
 * Delete a watchlist
 */
export async function deleteWatchlist(id: number): Promise<void> {
  return apiPost<void>(`${BASE_URL}/${id}/delete`, {});
}

/**
 * Clone a watchlist
 */
export async function cloneWatchlist(id: number, data: WatchlistCloneRequest): Promise<Watchlist> {
  return apiPost<Watchlist>(`${BASE_URL}/${id}/clone`, data);
}

/**
 * Get symbols for a watchlist
 */
export async function listWatchlistSymbols(id: number): Promise<WatchlistSymbolsResponse> {
  return apiGet<WatchlistSymbolsResponse>(`${BASE_URL}/${id}/symbols`);
}

/**
 * Add a symbol to a watchlist
 */
export async function addWatchlistSymbol(
  id: number,
  data: WatchlistSymbolAddRequest
): Promise<WatchlistSymbolAddResponse> {
  return apiPost<WatchlistSymbolAddResponse>(`${BASE_URL}/${id}/symbols`, data);
}

/**
 * Remove a symbol from a watchlist
 */
export async function removeWatchlistSymbol(
  watchlistId: number,
  symbolId: number
): Promise<WatchlistSymbolRemoveResponse> {
  return apiPost<WatchlistSymbolRemoveResponse>(
    `${BASE_URL}/${watchlistId}/symbols/${symbolId}/delete`,
    {}
  );
}

/**
 * List all categories
 */
export async function listCategories(): Promise<Category[]> {
  return apiGet<Category[]>(`${BASE_URL}/categories`);
}

/**
 * Create a new category
 */
export async function createCategory(data: CategoryCreate): Promise<Category> {
  return apiPost<Category>(`${BASE_URL}/categories`, data);
}

/**
 * Delete a category
 */
export async function deleteCategory(id: number): Promise<void> {
  return apiPost<void>(`${BASE_URL}/categories/${id}/delete`, {});
}
