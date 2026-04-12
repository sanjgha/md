/**
 * Tests for Edit Watchlist Modal
 *
 * TDD: These tests verify the edit watchlist modal functionality
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@solidjs/testing-library';
import { ShowEditWatchlistModal } from '~/pages/watchlists/edit-modal';
import type { Category, Watchlist } from '~/pages/watchlists/types';

// Mock the watchlistsAPI
vi.mock('~/lib/watchlists-api', () => ({
  watchlistsAPI: {
    update: vi.fn(),
    get: vi.fn(),
    categories: {
      list: vi.fn(),
    },
  },
}));

describe('ShowEditWatchlistModal', () => {
  const mockCategories: Category[] = [
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

  const mockOnClose = vi.fn();
  const mockOnSuccess = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('when opened', () => {
    it('should render modal with form pre-filled', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.categories.list).mockResolvedValue(mockCategories);

      render(() => (
        <ShowEditWatchlistModal
          isOpen={true}
          watchlistId={1}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      ));

      await waitFor(() => {
        expect(screen.getByText(/edit watchlist/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/category/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
      });
    });

    it('should load categories on mount', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.categories.list).mockResolvedValue(mockCategories);

      render(() => (
        <ShowEditWatchlistModal
          isOpen={true}
          watchlistId={1}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      ));

      await waitFor(() => {
        expect(watchlistsAPI.categories.list).toHaveBeenCalled();
      });
    });
  });

  describe('pre-filling data', () => {
    it('should pre-fill form with watchlist data', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.get).mockResolvedValue(mockWatchlist);
      vi.mocked(watchlistsAPI.categories.list).mockResolvedValue(mockCategories);

      render(() => (
        <ShowEditWatchlistModal
          isOpen={true}
          watchlistId={1}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      ));

      await waitFor(() => {
        const nameInput = screen.getByLabelText(/name/i) as HTMLInputElement;
        const descriptionInput = screen.getByLabelText(/description/i) as HTMLTextAreaElement;
        const categorySelect = screen.getByLabelText(/category/i) as HTMLSelectElement;

        expect(nameInput.value).toBe('Tech Stocks');
        expect(descriptionInput.value).toBe('Technology companies');
        expect(categorySelect.value).toBe('1');
      });
    });
  });

  describe('form validation', () => {
    it('should show error when name is empty after edit', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.get).mockResolvedValue(mockWatchlist);
      vi.mocked(watchlistsAPI.categories.list).mockResolvedValue(mockCategories);

      render(() => (
        <ShowEditWatchlistModal
          isOpen={true}
          watchlistId={1}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      ));

      await waitFor(() => {
        expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
      });

      // Clear the name
      const nameInput = screen.getByLabelText(/name/i);
      fireEvent.input(nameInput, { target: { value: '' } });

      // Try to submit
      const submitButton = screen.getByRole('button', { name: /save/i });
      submitButton.click();

      await waitFor(() => {
        expect(screen.getByText(/name is required/i)).toBeInTheDocument();
      });
    });

    it('should disable submit button while loading', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.get).mockResolvedValue(mockWatchlist);
      vi.mocked(watchlistsAPI.categories.list).mockResolvedValue(mockCategories);
      vi.mocked(watchlistsAPI.update).mockReturnValue(
        new Promise(() => {}) // Never resolves
      );

      render(() => (
        <ShowEditWatchlistModal
          isOpen={true}
          watchlistId={1}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      ));

      await waitFor(() => {
        expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
      });

      const submitButton = screen.getByRole('button', { name: /save/i });
      submitButton.click();

      await waitFor(() => {
        expect(submitButton).toBeDisabled();
      });
    });
  });

  describe('successful update', () => {
    it('should call update API with form data', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.get).mockResolvedValue(mockWatchlist);
      vi.mocked(watchlistsAPI.categories.list).mockResolvedValue(mockCategories);
      vi.mocked(watchlistsAPI.update).mockResolvedValue({
        ...mockWatchlist,
        name: 'Updated Tech Stocks',
      });

      render(() => (
        <ShowEditWatchlistModal
          isOpen={true}
          watchlistId={1}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      ));

      await waitFor(() => {
        expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
        const submitButton = screen.getByRole('button', { name: /save/i });
        expect(submitButton).toBeInTheDocument();
        expect(submitButton).not.toBeDisabled();
      });

      // Update the name
      const nameInput = screen.getByLabelText(/name/i);
      fireEvent.input(nameInput, { target: { value: 'Updated Tech Stocks' } });

      // Submit the form via button click
      const submitButton = screen.getByRole('button', { name: /save/i });
      submitButton.click();

      // Wait for API call
      await waitFor(
        () => {
          expect(watchlistsAPI.update).toHaveBeenCalled();
        },
        { timeout: 5000 }
      );
    });

    it('should call onClose and onSuccess after successful update', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.get).mockResolvedValue(mockWatchlist);
      vi.mocked(watchlistsAPI.categories.list).mockResolvedValue(mockCategories);
      vi.mocked(watchlistsAPI.update).mockResolvedValue(mockWatchlist);

      render(() => (
        <ShowEditWatchlistModal
          isOpen={true}
          watchlistId={1}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      ));

      await waitFor(() => {
        expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
      });

      const submitButton = screen.getByRole('button', { name: /save/i });
      submitButton.click();

      await waitFor(() => {
        expect(mockOnSuccess).toHaveBeenCalled();
        expect(mockOnClose).toHaveBeenCalled();
      });
    });
  });

  describe('when closed', () => {
    it('should not render when isOpen is false', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.get).mockResolvedValue(mockWatchlist);
      vi.mocked(watchlistsAPI.categories.list).mockResolvedValue(mockCategories);

      render(() => (
        <ShowEditWatchlistModal
          isOpen={false}
          watchlistId={1}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      ));

      expect(screen.queryByText(/edit watchlist/i)).not.toBeInTheDocument();
    });

    it('should call onClose when cancel is clicked', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.get).mockResolvedValue(mockWatchlist);
      vi.mocked(watchlistsAPI.categories.list).mockResolvedValue(mockCategories);

      render(() => (
        <ShowEditWatchlistModal
          isOpen={true}
          watchlistId={1}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      ));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
      });

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      cancelButton.click();

      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  describe('error handling', () => {
    it('should display error message when API fails', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.get).mockResolvedValue(mockWatchlist);
      vi.mocked(watchlistsAPI.categories.list).mockResolvedValue(mockCategories);
      vi.mocked(watchlistsAPI.update).mockRejectedValue(
        new Error('Failed to update watchlist')
      );

      render(() => (
        <ShowEditWatchlistModal
          isOpen={true}
          watchlistId={1}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      ));

      await waitFor(() => {
        expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
      });

      const submitButton = screen.getByRole('button', { name: /save/i });
      submitButton.click();

      await waitFor(() => {
        expect(screen.getByText(/failed to update watchlist/i)).toBeInTheDocument();
      });
    });
  });
});
