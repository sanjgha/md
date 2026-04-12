/**
 * Tests for Watchlist Dashboard component
 *
 * TDD: These tests verify the dashboard displays watchlists grouped by category
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@solidjs/testing-library';
import { ShowWatchlistsDashboard } from '~/pages/watchlists/dashboard';
import type { CategoryWatchlists } from '~/pages/watchlists/types';

// Mock the watchlistsAPI
vi.mock('~/lib/watchlists-api', () => ({
  watchlistsAPI: {
    list: vi.fn(),
  },
}));

describe('ShowWatchlistsDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('when loading', () => {
    it('should show loading state', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.list).mockReturnValue(
        new Promise(() => {}) // Never resolves
      );

      render(() => <ShowWatchlistsDashboard />);

      expect(screen.getByText(/loading/i)).toBeInTheDocument();
    });
  });

  describe('when data loads successfully', () => {
    it('should display watchlists grouped by category', async () => {
      const mockData: { categories: CategoryWatchlists[] } = {
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

      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.list).mockResolvedValue(mockData);

      render(() => <ShowWatchlistsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('Active Trading')).toBeInTheDocument();
        expect(screen.getByText('Momentum Plays')).toBeInTheDocument();
        expect(screen.getByText('5 stocks')).toBeInTheDocument();
      });
    });

    it('should display category icon', async () => {
      const mockData = {
        categories: [
          {
            category_id: 1,
            category_name: 'Active Trading',
            category_icon: '🔥',
            is_system: true,
            watchlists: [],
          },
        ],
      };

      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.list).mockResolvedValue(mockData);

      render(() => <ShowWatchlistsDashboard />);

      await waitFor(() => {
        expect(screen.getByText('🔥')).toBeInTheDocument();
      });
    });

    it('should display badge for auto-generated watchlists', async () => {
      const mockData = {
        categories: [
          {
            category_id: 2,
            category_name: 'Scanner Results',
            category_icon: '📊',
            is_system: true,
            watchlists: [
              {
                id: 2,
                name: 'Price Action - Today',
                category_id: 2,
                description: null,
                is_auto_generated: true,
                scanner_name: 'price_action',
                watchlist_mode: 'replace',
                source_scan_date: '2026-04-12',
                created_at: '2026-04-12T00:00:00Z',
                updated_at: '2026-04-12T00:00:00Z',
                symbol_count: 3,
              },
            ],
          },
        ],
      };

      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.list).mockResolvedValue(mockData);

      render(() => <ShowWatchlistsDashboard />);

      await waitFor(() => {
        expect(screen.getByText(/auto-generated/i)).toBeInTheDocument();
      });
    });

    it('should show "New Watchlist" button', async () => {
      const mockData = { categories: [] };

      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.list).mockResolvedValue(mockData);

      render(() => <ShowWatchlistsDashboard />);

      await waitFor(() => {
        expect(screen.getByText(/new watchlist/i)).toBeInTheDocument();
      });
    });
  });

  describe('when API fails', () => {
    it('should display error message', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.list).mockRejectedValue(
        new Error('Failed to fetch')
      );

      render(() => <ShowWatchlistsDashboard />);

      await waitFor(() => {
        expect(screen.getByText(/failed to load watchlists/i)).toBeInTheDocument();
      });
    });
  });

  describe('when no watchlists exist', () => {
    it('should display empty state', async () => {
      const mockData = { categories: [] };

      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.list).mockResolvedValue(mockData);

      render(() => <ShowWatchlistsDashboard />);

      await waitFor(() => {
        expect(screen.getByText(/no watchlists yet/i)).toBeInTheDocument();
      });
    });
  });
});
