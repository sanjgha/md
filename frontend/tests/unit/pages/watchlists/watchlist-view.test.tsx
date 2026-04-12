/**
 * Tests for Watchlist Split-View Component
 *
 * TDD: These tests verify the split-view displays stocks and chart placeholder
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@solidjs/testing-library';
import { ShowWatchlistView } from '~/pages/watchlists/watchlist-view';
import type { Watchlist, WatchlistSymbol } from '~/pages/watchlists/types';

// Mock the watchlistsAPI
vi.mock('~/lib/watchlists-api', () => ({
  watchlistsAPI: {
    get: vi.fn(),
    symbols: {
      list: vi.fn(),
      remove: vi.fn(),
    },
  },
}));

// Mock the router
vi.mock('@solidjs/router', () => ({
  useParams: () => ({ id: '1' }),
}));

describe('ShowWatchlistView', () => {
  const mockWatchlist: Watchlist = {
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

  const mockSymbols: WatchlistSymbol[] = [
    {
      id: 1,
      stock_id: 1,
      symbol: 'AAPL',
      name: 'Apple Inc',
      notes: 'Strong momentum',
      priority: 0,
      added_at: '2026-04-12T00:00:00Z',
    },
    {
      id: 2,
      stock_id: 2,
      symbol: 'MSFT',
      name: 'Microsoft Corp',
      notes: null,
      priority: 0,
      added_at: '2026-04-12T00:00:00Z',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('when loading', () => {
    it('should show loading state', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.get).mockReturnValue(
        new Promise(() => {}) // Never resolves
      );

      render(() => <ShowWatchlistView />);

      expect(screen.getByText(/loading/i)).toBeInTheDocument();
    });
  });

  describe('when data loads successfully', () => {
    it('should display watchlist name', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.get).mockResolvedValue(mockWatchlist);
      vi.mocked(watchlistsAPI.symbols.list).mockResolvedValue({
        symbols: mockSymbols,
      });

      render(() => <ShowWatchlistView />);

      await waitFor(() => {
        expect(screen.getByText('Tech Stocks')).toBeInTheDocument();
      });
    });

    it('should display watchlist description', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.get).mockResolvedValue(mockWatchlist);
      vi.mocked(watchlistsAPI.symbols.list).mockResolvedValue({
        symbols: mockSymbols,
      });

      render(() => <ShowWatchlistView />);

      await waitFor(() => {
        expect(screen.getByText('Technology companies')).toBeInTheDocument();
      });
    });

    it('should display all symbols in stock list', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.get).mockResolvedValue(mockWatchlist);
      vi.mocked(watchlistsAPI.symbols.list).mockResolvedValue({
        symbols: mockSymbols,
      });

      render(() => <ShowWatchlistView />);

      await waitFor(() => {
        expect(screen.getByText('AAPL')).toBeInTheDocument();
        expect(screen.getByText('MSFT')).toBeInTheDocument();
      });
    });

    it('should display symbol notes when present', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.get).mockResolvedValue(mockWatchlist);
      vi.mocked(watchlistsAPI.symbols.list).mockResolvedValue({
        symbols: mockSymbols,
      });

      render(() => <ShowWatchlistView />);

      await waitFor(() => {
        expect(screen.getByText('Strong momentum')).toBeInTheDocument();
      });
    });

    it('should show empty chart pane when no symbol selected', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.get).mockResolvedValue(mockWatchlist);
      vi.mocked(watchlistsAPI.symbols.list).mockResolvedValue({
        symbols: mockSymbols,
      });

      render(() => <ShowWatchlistView />);

      await waitFor(() => {
        expect(screen.getByText(/select a stock to view chart/i)).toBeInTheDocument();
      });
    });

    it('should show chart placeholder when symbol is selected', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.get).mockResolvedValue(mockWatchlist);
      vi.mocked(watchlistsAPI.symbols.list).mockResolvedValue({
        symbols: mockSymbols,
      });

      render(() => <ShowWatchlistView />);

      // Wait for initial render
      await waitFor(() => {
        expect(screen.getByText('AAPL')).toBeInTheDocument();
      });

      // Click on AAPL
      const aaplButton = screen.getByText('AAPL');
      aaplButton.click();

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: 'AAPL' })).toBeInTheDocument();
        expect(screen.getByText(/chart will appear here/i)).toBeInTheDocument();
      });
    });

    it('should display auto-generated badge if applicable', async () => {
      const autoGeneratedWatchlist = { ...mockWatchlist, is_auto_generated: true };
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.get).mockResolvedValue(autoGeneratedWatchlist);
      vi.mocked(watchlistsAPI.symbols.list).mockResolvedValue({
        symbols: [],
      });

      render(() => <ShowWatchlistView />);

      await waitFor(() => {
        expect(screen.getByText(/auto-generated/i)).toBeInTheDocument();
      });
    });
  });

  describe('when API fails', () => {
    it('should display error message', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.get).mockRejectedValue(
        new Error('Failed to fetch')
      );

      render(() => <ShowWatchlistView />);

      await waitFor(() => {
        expect(screen.getByText(/failed to load watchlist/i)).toBeInTheDocument();
      });
    });
  });

  describe('when no symbols in watchlist', () => {
    it('should display empty state', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.get).mockResolvedValue(mockWatchlist);
      vi.mocked(watchlistsAPI.symbols.list).mockResolvedValue({
        symbols: [],
      });

      render(() => <ShowWatchlistView />);

      await waitFor(() => {
        expect(screen.getByText(/no symbols in this watchlist/i)).toBeInTheDocument();
      });
    });
  });
});
