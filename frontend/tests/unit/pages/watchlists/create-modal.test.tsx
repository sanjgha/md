/**
 * Tests for Create Watchlist Modal
 *
 * TDD: These tests verify the create watchlist modal functionality
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@solidjs/testing-library';
import { ShowCreateWatchlistModal } from '~/pages/watchlists/create-modal';
import type { Category } from '~/pages/watchlists/types';

// Mock the watchlistsAPI
vi.mock('~/lib/watchlists-api', () => ({
  watchlistsAPI: {
    create: vi.fn(),
    categories: {
      list: vi.fn(),
    },
  },
}));

describe('ShowCreateWatchlistModal', () => {
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
    {
      id: 2,
      name: 'Research',
      description: null,
      color: null,
      icon: '🔬',
      created_at: '2026-04-12T00:00:00Z',
      updated_at: '2026-04-12T00:00:00Z',
    },
  ];

  const mockOnClose = vi.fn();
  const mockOnSuccess = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('when opened', () => {
    it('should render modal with form', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.categories.list).mockResolvedValue(mockCategories);

      render(() => (
        <ShowCreateWatchlistModal
          isOpen={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      ));

      await waitFor(() => {
        expect(screen.getByText(/create watchlist/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/category/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/description/i)).toBeInTheDocument();
      });
    });

    it('should load categories on mount', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.categories.list).mockResolvedValue(mockCategories);

      render(() => (
        <ShowCreateWatchlistModal
          isOpen={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      ));

      await waitFor(() => {
        expect(watchlistsAPI.categories.list).toHaveBeenCalled();
      });
    });

    it('should display category options', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.categories.list).mockResolvedValue(mockCategories);

      render(() => (
        <ShowCreateWatchlistModal
          isOpen={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      ));

      await waitFor(() => {
        expect(screen.getByText('🔥 Active Trading')).toBeInTheDocument();
        expect(screen.getByText('🔬 Research')).toBeInTheDocument();
      });
    });
  });

  describe('form validation', () => {
    it('should show error when name is empty', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.categories.list).mockResolvedValue(mockCategories);

      render(() => (
        <ShowCreateWatchlistModal
          isOpen={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      ));

      // Wait for modal to load completely
      await waitFor(() => {
        expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
      });

      // Try to submit without entering a name
      const submitButton = screen.getByRole('button', { name: /create/i });
      submitButton.click();

      await waitFor(() => {
        expect(screen.getByText(/name is required/i)).toBeInTheDocument();
      });
    });

    it('should disable submit button while loading', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.categories.list).mockResolvedValue(mockCategories);
      vi.mocked(watchlistsAPI.create).mockReturnValue(
        new Promise(() => {}) // Never resolves
      );

      render(() => (
        <ShowCreateWatchlistModal
          isOpen={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      ));

      await waitFor(() => {
        expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
      });

      // Fill in the form
      const nameInput = screen.getByLabelText(/name/i);
      fireEvent.input(nameInput, { target: { value: 'Test Watchlist' } });

      const submitButton = screen.getByRole('button', { name: /create/i });
      submitButton.click();

      await waitFor(() => {
        expect(submitButton).toBeDisabled();
      });
    });
  });

  describe('successful creation', () => {
    it('should call create API with form data', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.categories.list).mockResolvedValue(mockCategories);
      vi.mocked(watchlistsAPI.create).mockResolvedValue({
        id: 1,
        name: 'Test Watchlist',
        category_id: 1,
        description: 'Test description',
        is_auto_generated: false,
        scanner_name: null,
        watchlist_mode: 'manual',
        source_scan_date: null,
        created_at: '2026-04-12T00:00:00Z',
        updated_at: '2026-04-12T00:00:00Z',
        symbols: [],
      });

      render(() => (
        <ShowCreateWatchlistModal
          isOpen={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      ));

      await waitFor(() => {
        expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
      });

      // Fill in the form
      const nameInput = screen.getByLabelText(/name/i);
      const descriptionInput = screen.getByLabelText(/description/i);
      const categorySelect = screen.getByLabelText(/category/i);

      fireEvent.input(nameInput, { target: { value: 'Test Watchlist' } });
      fireEvent.input(descriptionInput, { target: { value: 'Test description' } });
      fireEvent.change(categorySelect, { target: { value: '1' } });

      // Submit
      const submitButton = screen.getByRole('button', { name: /create/i });
      submitButton.click();

      await waitFor(() => {
        expect(watchlistsAPI.create).toHaveBeenCalledWith({
          name: 'Test Watchlist',
          category_id: 1,
          description: 'Test description',
        });
      });
    });

    it('should call onClose and onSuccess after successful creation', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.categories.list).mockResolvedValue(mockCategories);
      vi.mocked(watchlistsAPI.create).mockResolvedValue({
        id: 1,
        name: 'Test Watchlist',
        category_id: 1,
        description: null,
        is_auto_generated: false,
        scanner_name: null,
        watchlist_mode: 'manual',
        source_scan_date: null,
        created_at: '2026-04-12T00:00:00Z',
        updated_at: '2026-04-12T00:00:00Z',
        symbols: [],
      });

      render(() => (
        <ShowCreateWatchlistModal
          isOpen={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      ));

      await waitFor(() => {
        expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
      });

      // Fill and submit
      const nameInput = screen.getByLabelText(/name/i);
      fireEvent.input(nameInput, { target: { value: 'Test' } });

      const submitButton = screen.getByRole('button', { name: /create/i });
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
      vi.mocked(watchlistsAPI.categories.list).mockResolvedValue(mockCategories);

      render(() => (
        <ShowCreateWatchlistModal
          isOpen={false}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      ));

      expect(screen.queryByText(/create watchlist/i)).not.toBeInTheDocument();
    });

    it('should call onClose when cancel is clicked', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.categories.list).mockResolvedValue(mockCategories);

      render(() => (
        <ShowCreateWatchlistModal
          isOpen={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      ));

      await waitFor(() => {
        expect(screen.getByText(/cancel/i)).toBeInTheDocument();
      });

      const cancelButton = screen.getByRole('button', { name: /cancel/i });
      cancelButton.click();

      expect(mockOnClose).toHaveBeenCalled();
    });

    it('should call onClose when X button is clicked', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.categories.list).mockResolvedValue(mockCategories);

      render(() => (
        <ShowCreateWatchlistModal
          isOpen={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      ));

      await waitFor(() => {
        expect(screen.getByText(/create watchlist/i)).toBeInTheDocument();
      });

      const closeButton = screen.getByRole('button', { name: /close/i });
      closeButton.click();

      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  describe('error handling', () => {
    it('should display error message when API fails', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.categories.list).mockResolvedValue(mockCategories);
      vi.mocked(watchlistsAPI.create).mockRejectedValue(
        new Error('Failed to create watchlist')
      );

      render(() => (
        <ShowCreateWatchlistModal
          isOpen={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      ));

      await waitFor(() => {
        expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
      });

      // Fill and submit
      const nameInput = screen.getByLabelText(/name/i);
      fireEvent.input(nameInput, { target: { value: 'Test' } });

      const submitButton = screen.getByRole('button', { name: /create/i });
      submitButton.click();

      await waitFor(() => {
        expect(screen.getByText(/failed to create watchlist/i)).toBeInTheDocument();
      });
    });

    it('should re-enable submit button after error', async () => {
      const { watchlistsAPI } = await import('~/lib/watchlists-api');
      vi.mocked(watchlistsAPI.categories.list).mockResolvedValue(mockCategories);
      vi.mocked(watchlistsAPI.create).mockRejectedValue(
        new Error('Failed to create watchlist')
      );

      render(() => (
        <ShowCreateWatchlistModal
          isOpen={true}
          onClose={mockOnClose}
          onSuccess={mockOnSuccess}
        />
      ));

      await waitFor(() => {
        expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
      });

      // Fill and submit
      const nameInput = screen.getByLabelText(/name/i);
      fireEvent.input(nameInput, { target: { value: 'Test' } });

      const submitButton = screen.getByRole('button', { name: /create/i });
      submitButton.click();

      await waitFor(() => {
        expect(screen.getByText(/failed to create watchlist/i)).toBeInTheDocument();
        expect(submitButton).not.toBeDisabled();
      });
    });
  });
});
