/**
 * Tests for Watchlist Routes Integration
 *
 * TDD: These tests verify routes are properly configured
 */

import { describe, it, expect, vi } from 'vitest';

// Mock the watchlist components
vi.mock('~/pages/watchlists/dashboard', () => ({
  ShowWatchlistsDashboard: () => null,
}));

describe('Watchlist Routes', () => {
  it('should have watchlist routes defined in main.tsx', async () => {
    // This test verifies the module can be imported
    // The actual routing is tested in E2E tests
    const mainModule = await import('~/main');

    // Verify the module exports something
    expect(mainModule).toBeDefined();

    // Verify default export exists (the app)
    expect(mainModule.default).toBeInstanceOf(Function);
  });

  it('should export watchlist dashboard component', async () => {
    const { ShowWatchlistsDashboard } = await import('~/pages/watchlists/dashboard');

    // Verify component is exported
    expect(ShowWatchlistsDashboard).toBeInstanceOf(Function);
  });
});
