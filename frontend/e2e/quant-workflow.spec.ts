import { expect, test, type Page } from "@playwright/test";

const user = {
  id: 7,
  username: "quant-tester",
  is_admin: false,
  must_change_password: false,
};

const run = {
  id: "run-one",
  name: "消费龙头回测",
  status: "succeeded",
  attempts: 1,
  created_at: 1_786_000_000,
  updated_at: 1_786_000_010,
  completed_at: 1_786_000_010,
  request: {
    name: "消费龙头回测",
    universe: { source: "custom", codes: ["600519"] },
    strategy: {
      type: "ma_cross",
      version: "1.0.0",
      name: "双均线趋势",
      parameters: { fast_period: 5, slow_period: 20 },
    },
    start_date: "2025-01-01",
    end_date: "2026-01-01",
    benchmark: "000300",
  },
  result: {
    engine_version: "v1",
    data_hash: "hash",
    data_sources: ["tencent"],
    codes: ["600519"],
    metrics: {
      total_return: 12.34,
      annualized_return: 11.2,
      annualized_volatility: 10,
      benchmark_return: 8,
      excess_return: 4.34,
      max_drawdown: -5.2,
      profit_loss_ratio: 1.8,
      sharpe_ratio: 1.1,
      turnover_rate: 100,
      trade_count: 1,
      win_rate: 60,
    },
    equity_curve: [],
    monthly_returns: [],
    trades: [],
  },
};

async function mockQuantApi(page: Page) {
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\//, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(user) });
  });
  await page.route("**/api/quant/strategy-presets", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\/quant\/strategies$/, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\/quant\/backtests$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [run] }),
    });
  });
  await page.route("**/api/quant/backtests/run-one", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(run) });
  });
}

test("splits the desktop quant workflow and keeps task cards aligned", async ({ page }) => {
  await mockQuantApi(page);
  await page.goto("/quant");

  await expect(page.getByRole("region", { name: "量化回测配置" })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "已保存策略" })).toBeHidden();
  await expect(page.getByText("当前策略：双均线趋势")).toBeVisible();

  await page.getByRole("tab", { name: /任务记录/ }).click();
  const currentBox = await page.locator(".quant-run-summary-card").boundingBox();
  const historyBox = await page.locator(".quant-history-card").boundingBox();
  expect(currentBox).not.toBeNull();
  expect(historyBox).not.toBeNull();
  expect(Math.abs((currentBox?.y ?? 0) - (historyBox?.y ?? 0))).toBeLessThanOrEqual(2);

  await page.getByRole("button", { name: "查看回测 消费龙头回测" }).click();
  await expect(page.getByRole("region", { name: "回测结果分析" })).toBeVisible();
  await expect(page.getByText("当前结果", { exact: true })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "回测结果导航" })).toBeVisible();

  await page.getByRole("tab", { name: /配置回测/ }).click();
  await expect(page.getByRole("region", { name: "量化回测配置" })).toBeVisible();
  await expect(page.getByRole("region", { name: "回测结果分析" })).toHaveCount(0);
});

test("uses one-panel mobile navigation without horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockQuantApi(page);
  await page.goto("/quant");

  const panelSelect = page.getByRole("combobox", { name: "量化回测视图" });
  await panelSelect.click();
  await panelSelect.press("ArrowDown");
  await panelSelect.press("Enter");
  await expect(page.getByRole("region", { name: "回测任务工作台" })).toBeVisible();

  const currentBox = await page.locator(".quant-run-summary-card").boundingBox();
  const historyBox = await page.locator(".quant-history-card").boundingBox();
  expect((historyBox?.y ?? 0)).toBeGreaterThan((currentBox?.y ?? 0));
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);

  await panelSelect.click();
  await panelSelect.press("ArrowUp");
  await panelSelect.press("Enter");
  const submitBarPosition = await page.locator(".quant-submit-bar").evaluate(
    (element) => getComputedStyle(element).position,
  );
  expect(submitBarPosition).toBe("sticky");
});
