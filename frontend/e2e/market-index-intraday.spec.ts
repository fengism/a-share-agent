import { expect, test } from "@playwright/test";

const user = { id: 7, username: "researcher", is_admin: false, must_change_password: false };

test("switches the index intraday chart without hiding K-line", async ({ page }) => {
  const requestedSymbols: string[] = [];
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\//, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(user) });
  });
  await page.route("**/api/market/indices", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        source: "mock",
        indices: [
          { code: "000001", name: "上证指数", price: 3200, change_pct: 0.5, amount: 100000000 },
          { code: "399001", name: "深证成指", price: 11000, change_pct: -0.2, amount: 200000000 },
        ],
      }),
    });
  });
  await page.route("**/api/market/index-intraday?**", async (route) => {
    const symbol = new URL(route.request().url()).searchParams.get("symbol") || "";
    requestedSymbols.push(symbol);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: symbol,
        source: "sina_direct",
        prev_close: null,
        items: [
          { time: "09:30:00", price: 3200, avg_price: 3198, volume: 100, amount: null, change_pct: null },
          { time: "09:31:00", price: 3202, avg_price: 3199, volume: 80, amount: null, change_pct: null },
        ],
      }),
    });
  });
  await page.route("**/api/market/index-kline?**", async (route) => {
    const symbol = new URL(route.request().url()).searchParams.get("symbol") || "";
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: symbol,
        period: "daily",
        adjust: "",
        source: "mock",
        adjustment_verified: true,
        items: [{ date: "2026-08-20", open: 1, close: 2, high: 2, low: 1, volume: 10, amount: 20 }],
      }),
    });
  });

  await page.goto("/market?tab=a-index");
  await expect(page.locator(".index-intraday-card")).toContainText("上证指数 分时");
  await expect(page.getByText("上证指数 · K线趋势")).toBeVisible();
  await expect.poll(() => requestedSymbols).toContain("000001");

  await page.getByRole("button", { name: /深证成指/ }).click();
  await expect(page.locator(".index-intraday-card")).toContainText("深证成指 分时");
  await expect(page.getByText("深证成指 · K线趋势")).toBeVisible();
  await expect.poll(() => requestedSymbols).toContain("399001");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});
