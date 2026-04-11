import { test, expect } from "@playwright/test";

test.describe("Foundation smoke test", () => {
  test.beforeAll(async ({ request }) => {
    const health = await request.get("http://127.0.0.1:8001/api/health");
    expect(health.ok()).toBeTruthy();
  });

  test("unauthenticated redirect to /login", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
  });

  test("login with valid credentials redirects to /dashboard", async ({ page }) => {
    await page.goto("/login");
    await page.fill('input[autocomplete="username"]', "admin");
    await page.fill('input[autocomplete="current-password"]', "adminpass123");
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.locator("h1")).toContainText("Dashboard");
  });

  test("navigate to settings and verify appearance panel loads", async ({ page }) => {
    await page.goto("/login");
    await page.fill('input[autocomplete="username"]', "admin");
    await page.fill('input[autocomplete="current-password"]', "adminpass123");
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/dashboard/);
    await page.click('a[href="/settings"]');
    await expect(page).toHaveURL(/\/settings\/appearance/);
    await expect(page.locator("h2")).toContainText("Appearance");
  });

  test("toggle theme to light, save, reload — theme persists", async ({ page }) => {
    await page.goto("/login");
    await page.fill('input[autocomplete="username"]', "admin");
    await page.fill('input[autocomplete="current-password"]', "adminpass123");
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/dashboard/);
    await page.goto("/settings/appearance");

    await page.click('input[value="light"]');
    await page.click('button[type="submit"]');
    await expect(page.locator('button[type="submit"]')).toHaveText("Save");

    await page.reload();
    await expect(page.locator('input[value="light"]')).toBeChecked();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  });
});
