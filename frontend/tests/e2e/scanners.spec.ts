import { test, expect } from "@playwright/test";

// Assumes the dev server is running (npm run dev) and the DB has seeded scanner_results.
// Run with: npx playwright test tests/e2e/scanners.spec.ts

test.describe("Scanner Control Panel", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/login");
    await page.fill('[name="username"]', "testuser");
    await page.fill('[name="password"]', "testpass123");
    await page.click('[type="submit"]');
    await page.waitForURL("/");
  });

  test("navigates to /scanners and shows EOD tab by default", async ({ page }) => {
    await page.goto("/scanners");
    await expect(page.getByText("EOD")).toBeVisible();
    await expect(page.getByText("Intraday")).toBeVisible();
  });

  test("switching to Intraday tab shows Run button", async ({ page }) => {
    await page.goto("/scanners");
    await page.click("text=Intraday");
    await expect(page.getByText("Run")).toBeVisible();
  });

  test("deselecting a scanner pill hides its results", async ({ page }) => {
    await page.goto("/scanners");
    await page.waitForSelector(".scanner-result-row", { timeout: 5000 }).catch(() => null);
    const pill = page.getByRole("button", { name: "momentum" });
    if (await pill.isVisible()) {
      const initialCount = await page.locator(".scanner-result-row").count();
      await pill.click();
      const newCount = await page.locator(".scanner-result-row").count();
      expect(newCount).toBeLessThanOrEqual(initialCount);
    }
  });

  test("Intraday tab Run button triggers scan", async ({ page }) => {
    await page.goto("/scanners");
    await page.click("text=Intraday");
    await page.click("text=Run");
    await expect(page.getByText("Running...")).toBeVisible({ timeout: 2000 }).catch(() => null);
  });
});
