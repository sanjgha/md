/**
 * Tests for watchlists API client
 *
 * TDD: These tests verify the API client methods match backend endpoints
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { apiFetch } from '~/lib/api';
import type {
  Watchlist,
  WatchlistCreate,
  Category,
  CategoryWatchlists,
} from '~/pages/watchlists/types';

// Mock the apiFetch function
vi.mock('~/lib/api', () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
  apiFetch: vi.fn(),
}));

describe('watchlistsAPI', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('list', () => {
    it('should fetch watchlists grouped by category', async () => {
      const mockResponse = {
        categories: [
          {
            category_id: 1,
            category_name: 'Active Trading',
            category_icon: '🔥',
            is_system: true,
            watchlists: [
              {
                id: 1,
                name: 'Momentum Plays',
                category_id: 1,
                description: 'High momentum stocks',
                is_auto_generated: false,
                scanner_name: null,
                watchlist_mode: 'manual',
                source_scan_date: null,
                created_at: '2026-04-12T00:00:00Z',
                updated_at: '2026-04-12T00:00:00Z',
                symbol_count: 5,
              },
            ],
          },
        ],
      };

      vi.mocked(apiFetch).mockResolvedValueOnce(mockResponse);

      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      const result = await watchlistsAPI.list();

      expect(apiFetch).toHaveBeenCalledWith('/api/watchlists');
      expect(result).toEqual(mockResponse);
    });
  });

  describe('create', () => {
    it('should create a new watchlist', async () => {
      const createData: WatchlistCreate = {
        name: 'Tech Stocks',
        category_id: 1,
        description: 'Technology companies',
      };

      const mockResponse: Watchlist = {
        id: 2,
        name: 'Tech Stocks',
        category_id: 1,
        description: 'Technology companies',
        is_auto_generated: false,
        scanner_name: null,
        watchlist_mode: 'manual',
        source_scan_date: null,
        created_at: '2026-04-12T00:00:00Z',
        updated_at: '2026-04-12T00:00:00Z',
        symbols: [],
      };

      vi.mocked(apiFetch).mockResolvedValueOnce(mockResponse);

      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      const result = await watchlistsAPI.create(createData);

      expect(apiFetch).toHaveBeenCalledWith('/api/watchlists', {
        method: 'POST',
        body: JSON.stringify(createData),
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('get', () => {
    it('should fetch a single watchlist by ID', async () => {
      const mockResponse: Watchlist = {
        id: 1,
        name: 'Tech Stocks',
        category_id: 1,
        description: 'Technology companies',
        is_auto_generated: false,
        scanner_name: null,
        watchlist_mode: 'manual',
        source_scan_date: null,
        created_at: '2026-04-12T00:00:00Z',
        updated_at: '2026-04-12T00:00:00Z',
        symbols: [],
      };

      vi.mocked(apiFetch).mockResolvedValueOnce(mockResponse);

      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      const result = await watchlistsAPI.get(1);

      expect(apiFetch).toHaveBeenCalledWith('/api/watchlists/1');
      expect(result).toEqual(mockResponse);
    });
  });

  describe('update', () => {
    it('should update an existing watchlist', async () => {
      const updateData = { name: 'Updated Name' };

      const mockResponse: Watchlist = {
        id: 1,
        name: 'Updated Name',
        category_id: 1,
        description: null,
        is_auto_generated: false,
        scanner_name: null,
        watchlist_mode: 'manual',
        source_scan_date: null,
        created_at: '2026-04-12T00:00:00Z',
        updated_at: '2026-04-12T01:00:00Z',
        symbols: [],
      };

      vi.mocked(apiFetch).mockResolvedValueOnce(mockResponse);

      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      const result = await watchlistsAPI.update(1, updateData);

      expect(apiFetch).toHaveBeenCalledWith('/api/watchlists/1', {
        method: 'PUT',
        body: JSON.stringify(updateData),
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('delete', () => {
    it('should delete a watchlist', async () => {
      vi.mocked(apiFetch).mockResolvedValueOnce(undefined);

      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      await watchlistsAPI.delete(1);

      expect(apiFetch).toHaveBeenCalledWith('/api/watchlists/1', {
        method: 'DELETE',
      });
    });
  });

  describe('symbols', () => {
    it('should list symbols in a watchlist', async () => {
      const mockResponse = [
        {
          id: 1,
          stock_id: 1,
          symbol: 'AAPL',
          name: 'Apple Inc',
          notes: 'Strong momentum',
          priority: 0,
          added_at: '2026-04-12T00:00:00Z',
        },
      ];

      vi.mocked(apiFetch).mockResolvedValueOnce(mockResponse);

      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      const result = await watchlistsAPI.symbols.list(1);

      expect(apiFetch).toHaveBeenCalledWith('/api/watchlists/1/symbols');
      expect(result).toEqual(mockResponse);
    });

    it('should add a symbol to a watchlist', async () => {
      vi.mocked(apiFetch).mockResolvedValueOnce({ success: true });

      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      await watchlistsAPI.symbols.add(1, 'AAPL', 'Good entry');

      expect(apiFetch).toHaveBeenCalledWith('/api/watchlists/1/symbols', {
        method: 'POST',
        body: JSON.stringify({ symbol: 'AAPL', notes: 'Good entry' }),
      });
    });

    it('should remove a symbol from a watchlist', async () => {
      vi.mocked(apiFetch).mockResolvedValueOnce({ success: true });

      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      await watchlistsAPI.symbols.remove(1, 'AAPL');

      expect(apiFetch).toHaveBeenCalledWith('/api/watchlists/1/symbols/AAPL', {
        method: 'DELETE',
      });
    });
  });

  describe('categories', () => {
    it('should list all categories', async () => {
      const mockResponse: Category[] = [
        {
          id: 1,
          name: 'Active Trading',
          description: null,
          color: null,
          icon: '🔥',
          created_at: '2026-04-12T00:00:00Z',
          updated_at: '2026-04-12T00:00:00Z',
        },
      ];

      vi.mocked(apiFetch).mockResolvedValueOnce(mockResponse);

      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      const result = await watchlistsAPI.categories.list();

      expect(apiFetch).toHaveBeenCalledWith('/api/watchlists/categories');
      expect(result).toEqual(mockResponse);
    });

    it('should create a new category', async () => {
      const createData = { name: 'My Category', icon: '🚀' };

      const mockResponse: Category = {
        id: 2,
        name: 'My Category',
        description: null,
        color: null,
        icon: '🚀',
        created_at: '2026-04-12T00:00:00Z',
        updated_at: '2026-04-12T00:00:00Z',
      };

      vi.mocked(apiFetch).mockResolvedValueOnce(mockResponse);

      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      const result = await watchlistsAPI.categories.create(createData);

      expect(apiFetch).toHaveBeenCalledWith('/api/watchlists/categories', {
        method: 'POST',
        body: JSON.stringify(createData),
      });
      expect(result).toEqual(mockResponse);
    });
  });

  describe('clone', () => {
    it('should clone a watchlist', async () => {
      const cloneData = { name: 'Copy of Tech Stocks' };

      const mockResponse: Watchlist = {
        id: 2,
        name: 'Copy of Tech Stocks',
        category_id: 1,
        description: null,
        is_auto_generated: false,
        scanner_name: null,
        watchlist_mode: 'manual',
        source_scan_date: null,
        created_at: '2026-04-12T00:00:00Z',
        updated_at: '2026-04-12T00:00:00Z',
        symbols: [],
      };

      vi.mocked(apiFetch).mockResolvedValueOnce(mockResponse);

      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      const result = await watchlistsAPI.clone(1, cloneData);

      expect(apiFetch).toHaveBeenCalledWith('/api/watchlists/1/clone', {
        method: 'POST',
        body: JSON.stringify(cloneData),
      });
      expect(result).toEqual(mockResponse);
    });
  });
});
