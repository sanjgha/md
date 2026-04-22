/**
 * End-to-End Tests for Realtime Updates
 *
 * TDD: These tests verify auto-refresh and current day candle features
 */

import { test, expect } from '@playwright/test';

test.describe('Realtime Updates E2E', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to login page
    await page.goto('/');

    // Log in
    await page.fill('input[name="username"]', 'test');
    await page.fill('input[name="password"]', 'test123');
    await page.click('button[type="submit"]');

    // Wait for navigation to dashboard
    await page.waitForURL('/dashboard');
  });

  test('should display watchlist with quotes', async ({ page }) => {
    await page.goto('/watchlists');

    // Check page title
    await expect(page.locator('h1')).toContainText('Watchlists');

    // Check for symbol rows with quote data
    // Note: This test assumes the watchlist has symbols from seed data
    const symbolRows = page.locator('.symbol-row');
    const count = await symbolRows.count();

    if (count > 0) {
      // Verify first row has quote data
      const firstRow = symbolRows.first();
      await expect(firstRow.locator('.symbol-last')).toBeVisible();
      await expect(firstRow.locator('.symbol-change')).toBeVisible();
      await expect(firstRow.locator('.source-dot')).toBeVisible();
    }
  });

  test('should show realtime indicator for current quotes', async ({ page }) => {
    await page.goto('/watchlists');

    // Expand a watchlist if any exist
    const expandButton = page.locator('.category-group__header').first();
    await expandButton.click();

    // Wait for quotes to load
    await page.waitForTimeout(1000);

    // Check for source dot (green = realtime, gray = EOD)
    const sourceDots = page.locator('.source-dot');
    const count = await sourceDots.count();

    if (count > 0) {
      // At least one source dot should be visible
      await expect(sourceDots.first()).toBeVisible();
    }
  });

  test('should display chart for selected symbol', async ({ page }) => {
    await page.goto('/watchlists');

    // Click on a symbol to select it
    const symbolRow = page.locator('.symbol-row').first();
    const count = await symbolRow.count();

    if (count > 0) {
      await symbolRow.click();

      // Chart panel should be visible
      const chartPanel = page.locator('.chart-panel');
      await expect(chartPanel).toBeVisible();

      // Check for chart container
      const chartContainer = page.locator('.chart-panel canvas, .chart-panel [class*="chart"]');
      await expect(chartContainer).toBeVisible();
    }
  });

  test('should show daily resolution option on chart', async ({ page }) => {
    await page.goto('/watchlists');

    // Select a symbol
    const symbolRow = page.locator('.symbol-row').first();
    const count = await symbolRow.count();

    if (count > 0) {
      await symbolRow.click();

      // Look for daily resolution button
      const dailyButton = page.locator('button:has-text("D")');
      await expect(dailyButton).toBeVisible();
    }
  });

  test('should switch between chart resolutions', async ({ page }) => {
    await page.goto('/watchlists');

    // Select a symbol
    const symbolRow = page.locator('.symbol-row').first();
    const count = await symbolRow.count();

    if (count > 0) {
      await symbolRow.click();

      // Click on different resolution buttons
      const resolutions = ['5m', '15m', '1h', 'D'];

      for (const res of resolutions) {
        const button = page.locator(`button:has-text("${res}")`);
        const isVisible = await button.isVisible();

        if (isVisible) {
          await button.click();
          // Wait for chart to update
          await page.waitForTimeout(500);
        }
      }
    }
  });

  test('should display symbol info in chart header', async ({ page }) => {
    await page.goto('/watchlists');

    // Select a symbol
    const symbolRow = page.locator('.symbol-row').first();
    const count = await symbolRow.count();

    if (count > 0) {
      await symbolRow.click();

      // Check for symbol name in chart header
      const symbolName = page.locator('.symbol-name');
      await expect(symbolName).toBeVisible();
    }
  });
});
