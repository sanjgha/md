/**
 * End-to-End Tests for Watchlist Workflow
 *
 * TDD: These tests verify the complete watchlist CRUD workflow through the UI
 */

import { test, expect } from '@playwright/test';

test.describe('Watchlist E2E Workflow', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to login page
    await page.goto('/');

    // Log in (assuming test user exists from seed)
    await page.fill('input[name="username"]', 'test');
    await page.fill('input[name="password"]', 'test123');
    await page.click('button[type="submit"]');

    // Wait for navigation to dashboard
    await page.waitForURL('/dashboard');
  });

  test('should display watchlists dashboard', async ({ page }) => {
    await page.goto('/watchlists');

    // Check page title
    await expect(page.locator('h1')).toContainText('Watchlists');

    // Check for "New Watchlist" button
    await expect(page.locator('button:has-text("New Watchlist")')).toBeVisible();
  });

  test('should create a new watchlist', async ({ page }) => {
    await page.goto('/watchlists');

    // Click "New Watchlist" button
    await page.click('button:has-text("New Watchlist")');

    // Wait for modal to appear
    await expect(page.locator('.modal-content')).toBeVisible();
    await expect(page.locator('h2')).toContainText('Create Watchlist');

    // Fill in the form
    await page.fill('#watchlist-name', 'My First Watchlist');
    await page.selectOption('#watchlist-category', '1'); // Active Trading
    await page.fill('#watchlist-description', 'Test watchlist for E2E testing');

    // Submit
    await page.click('button[type="submit"]:has-text("Create")');

    // Wait for modal to close
    await expect(page.locator('.modal-backdrop')).not.toBeVisible();

    // Verify the new watchlist appears (we'd need to mock or check database)
    // For now, just verify we're back on the dashboard
    await expect(page.locator('h1')).toContainText('Watchlists');
  });

  test('should validate required fields', async ({ page }) => {
    await page.goto('/watchlists');

    // Open create modal
    await page.click('button:has-text("New Watchlist")');

    // Try to submit without filling name
    const submitButton = page.locator('button[type="submit"]:has-text("Create")');
    await submitButton.click();

    // Should show validation error
    await expect(page.locator('.error-message')).toContainText('Name is required');
  });

  test('should close modal when cancel is clicked', async ({ page }) => {
    await page.goto('/watchlists');

    // Open modal
    await page.click('button:has-text("New Watchlist")');
    await expect(page.locator('.modal-content')).toBeVisible();

    // Click cancel
    await page.click('button:has-text("Cancel")');

    // Modal should close
    await expect(page.locator('.modal-backdrop')).not.toBeVisible();
  });

  test('should close modal when backdrop is clicked', async ({ page }) => {
    await page.goto('/watchlists');

    // Open modal
    await page.click('button:has-text("New Watchlist")');
    await expect(page.locator('.modal-content')).toBeVisible();

    // Click backdrop
    await page.click('.modal-backdrop');

    // Modal should close
    await expect(page.locator('.modal-backdrop')).not.toBeVisible();
  });

  test('should close modal with X button', async ({ page }) => {
    await page.goto('/watchlists');

    // Open modal
    await page.click('button:has-text("New Watchlist")');
    await expect(page.locator('.modal-content')).toBeVisible();

    // Click X button
    await page.click('.close-button');

    // Modal should close
    await expect(page.locator('.modal-backdrop')).not.toBeVisible();
  });

  test('should display error on API failure', async ({ page }) => {
    // Mock the API to fail
    await page.route('**/api/watchlists', route => route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'Internal server error' }),
    }));

    await page.goto('/watchlists');

    // Open modal
    await page.click('button:has-text("New Watchlist")');

    // Fill and submit
    await page.fill('#watchlist-name', 'Test Watchlist');
    await page.click('button[type="submit"]:has-text("Create")');

    // Should show error
    await expect(page.locator('.error-banner')).toBeVisible();
  });

  test('should navigate to watchlist detail view', async ({ page }) => {
    // First, we'd need to create a watchlist or mock the API
    // For now, let's just test navigation to a dummy ID
    await page.goto('/watchlists');

    // Click on a watchlist card (if any exist)
    // Since we might not have watchlists, let's test direct navigation
    await page.goto('/watchlists/1');

    // Should show watchlist view
    await expect(page.locator('.watchlist-view')).toBeVisible();
    await expect(page.locator('.watchlist-header h1')).toBeVisible();
  });

  test('should display empty state when no watchlists exist', async ({ page }) => {
    // Mock the API to return empty categories
    await page.route('**/api/watchlists', route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ categories: [] }),
    }));

    await page.goto('/watchlists');

    // Should show empty state
    await expect(page.locator('.empty-state')).toBeVisible();
    await expect(page.locator('text=No watchlists yet')).toBeVisible();
  });

  test('should show loading state while fetching', async ({ page }) => {
    // Mock the API to delay response
    await page.route('**/api/watchlists', async route => {
      await new Promise(resolve => setTimeout(resolve, 1000));
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ categories: [] }),
      });
    });

    await page.goto('/watchlists');

    // Should show loading state briefly
    await expect(page.locator('.loading')).toBeVisible();
  });
});
