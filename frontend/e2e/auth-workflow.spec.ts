import { expect, test, type Page } from "@playwright/test";

const user = {
  id: 7,
  username: "tester",
  is_admin: false,
  must_change_password: false,
};

async function routeFallbackApi(page: Page) {
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\//, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    const body = pathname === "/api/market/indices"
      ? { source: "mock", indices: [] }
      : pathname === "/api/market/index-intraday"
        ? { code: "000001", source: "sina_direct", prev_close: 3190, items: [{ time: "09:30:00", price: 3200, avg_price: 3198, volume: 100 }] }
        : pathname === "/api/stock/600519/intraday"
          ? { code: "600519", source: "mock", prev_close: null, items: [] }
        : pathname === "/api/watchlist"
        ? { source: "mock", quoted_at: "2026-01-03T10:00:00", items: [] }
        : [];
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
}

test("logs in through the authenticated browser flow", async ({ page }) => {
  await routeFallbackApi(page);
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ code: "auth.credentials_required", message: "未登录" }),
    });
  });
  await page.route("**/api/auth/login", async (route) => {
    expect(route.request().postDataJSON()).toEqual({ username: "tester", password: "password123" });
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ user }),
    });
  });

  await page.goto("/login");
  await page.getByPlaceholder("用户名").fill("tester");
  await page.getByPlaceholder("密码").fill("password123");
  await page.getByRole("button", { name: /登\s*录/ }).click();

  await expect(page).toHaveURL("/");
  await expect(page.getByRole("button", { name: "返回首页" })).toBeVisible();
  await expect(page.getByRole("main")).not.toContainText("页面加载失败");
});

test("reconnects a durable workflow and cancels it remotely", async ({ page }) => {
  await routeFallbackApi(page);
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(user) });
  });
  await page.route("**/api/stock/600519/info", (route) => route.fulfill({
    json: { code: "600519", name: "贵州茅台" },
  }));
  await page.route("**/api/stock/analysis-page/600519?include_market_data=false", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        stock_info: { code: "600519", name: "贵州茅台" },
        kline: null,
        intraday: null,
        valuation: null,
        cached_analysis: null,
        partial: false,
        unavailable_sections: [],
      }),
    });
  });
  await page.route("**/api/workflows/analysis/600519", async (route) => {
    await route.fulfill({
      status: 202,
      contentType: "application/json",
      body: JSON.stringify({ job: { id: "job-1" }, attached: false }),
    });
  });

  const cursors: Array<string | undefined> = [];
  await page.route("**/api/workflows/job-1/stream", async (route) => {
    cursors.push(route.request().headers()["last-event-id"]);
    const sequence = cursors.length;
    const agentPlanFrame = sequence === 1
      ? `id: 1:2\nevent: agent_event\ndata: ${JSON.stringify({
          type: "agent_event",
          total_stages: 3,
          agent_event: {
            type: "plan",
            plan: {
              summary: "先核验财务与估值，再检查风险",
              steps: [{
                id: "fundamental",
                title: "核验基本面",
                dependencies: [],
                status: "running",
                attempt: 1,
              }],
            },
          },
        })}\n\n`
      : "";
    await route.fulfill({
      status: 200,
      headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
      body: `id: 1:${sequence}\nevent: stage_started\ndata: ${JSON.stringify({
        type: "stage_started",
        stage: { stage: sequence, name: `阶段 ${sequence}`, status: "started" },
        total_stages: 7,
      })}\n\n${agentPlanFrame}`,
    });
  });

  let cancelled = false;
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\/workflows\/job-1$/, async (route) => {
    if (route.request().method() === "DELETE") cancelled = true;
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ id: "job-1", status: "cancelled" }),
    });
  });

  await page.goto("/analysis/600519");
  await page.getByRole("button", { name: "开始研究" }).click();
  await expect.poll(() => cursors.length).toBeGreaterThanOrEqual(2);
  expect(cursors[0]).toBeUndefined();
  expect(cursors[1]).toBe("1:2");
  await expect(page.getByText("Agent 思考与执行")).toBeVisible();
  const processToggle = page.getByRole("button", { name: /Agent 思考与执行/ });
  if (await processToggle.getAttribute("aria-expanded") === "false") await processToggle.click();
  await expect(page.getByText("先核验财务与估值，再检查风险")).toBeVisible();

  await page.getByRole("button", { name: "停止研究" }).click();
  await expect.poll(() => cancelled).toBe(true);
  await expect(page.getByText("已停止研究")).toBeVisible();
});

test("records a sell transaction from the current portfolio", async ({ page }) => {
  await routeFallbackApi(page);
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(user) });
  });
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\/portfolio$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        positions: [{
          id: 1,
          stock_code: "600519",
          stock_name: "贵州茅台",
          buy_price: 10,
          buy_time: "2026-01-02T09:30:00",
          shares: 60,
          current_price: 11,
          change_pct: 1,
          cost_value: 606,
          market_value: 660,
          profit_amount: 54,
          profit_pct: 8.91,
        }],
        stocks: [{
          stock_code: "600519",
          stock_name: "贵州茅台",
          position_count: 1,
          total_shares: 60,
          average_cost: 10.1,
          current_price: 11,
          change_pct: 1,
          cost_value: 606,
          market_value: 660,
          profit_amount: 54,
          profit_pct: 8.91,
          realized_profit_amount: 74,
          total_profit_amount: 128,
        }],
        transactions: [],
        closed_positions: [],
        summary: {
          stock_count: 1,
          position_count: 1,
          transaction_count: 2,
          total_cost: 606,
          priced_cost: 606,
          total_market_value: 660,
          total_profit_amount: 54,
          total_profit_pct: 8.91,
          unrealized_profit_amount: 54,
          realized_profit_amount: 74,
          combined_profit_amount: 128,
          profitable_count: 1,
          losing_count: 0,
          unpriced_count: 0,
        },
        risk: {
          largest_position_stock_code: "600519",
          largest_position_stock_name: "贵州茅台",
          max_single_stock_pct: 100,
          top3_concentration_pct: 100,
          concentration_level: "high",
          priced_stock_count: 1,
          unpriced_stock_count: 0,
          max_total_position_limit_pct: 80,
          max_single_stock_limit_pct: 30,
          max_sector_limit_pct: 40,
          largest_sector_name: null,
          largest_sector_pct: null,
          sector_allocations: [],
          warnings: ["单一股票仓位占比较高"],
        },
        settings: {
          initial_cash: null,
          max_total_position_pct: 80,
          max_single_stock_pct: 30,
          max_sector_pct: 40,
        },
        quoted_at: "2026-01-03T10:00:00",
        quote_source: "tencent",
        quote_stale: false,
      }),
    });
  });

  let submittedTransaction: Record<string, unknown> | undefined;
  await page.route("**/api/portfolio/transactions", async (route) => {
    submittedTransaction = route.request().postDataJSON();
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: 3,
        stock_code: "600519",
        stock_name: "贵州茅台",
        side: "sell",
        trade_price: 12,
        trade_time: submittedTransaction?.trade_time,
        shares: 40,
        fee: 0,
        note: "",
        created_at: "2026-01-03T10:00:00",
        matched_cost: 404,
        realized_profit_amount: 76,
        matches: [],
      }),
    });
  });

  await page.goto("/portfolio");
  await expect(page.getByRole("heading", { name: "仓位管理" })).toBeVisible();
  await page.getByRole("button", { name: "卖出 贵州茅台" }).click();
  await expect(page.getByRole("radio", { name: "卖出" })).toBeChecked();
  await expect(page.getByText(/贵州茅台.*可卖 60 股/).first()).toBeVisible();
  await expect(page.getByRole("spinbutton", { name: "卖出价" })).toHaveValue("11.0000");
  await page.getByRole("spinbutton", { name: "卖出价" }).fill("12");
  await page.getByRole("spinbutton", { name: /股数/ }).fill("40");
  await page.getByRole("button", { name: /记录卖出/ }).click();

  await expect.poll(() => submittedTransaction).toMatchObject({
    stock_code: "600519",
    side: "sell",
    trade_price: 12,
    shares: 40,
    fee: 0,
    note: "",
  });
});

test("places the Dashboard watchlist in a responsive right rail", async ({ page }) => {
  await routeFallbackApi(page);
  await page.route("**/api/market/indices", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ source: "腾讯", indices: [
        { code: "000001", name: "上证指数", price: 3200, change_pct: 0.5, amount: 100000000 },
        { code: "399001", name: "深证成指", price: 11000, change_pct: -0.2, amount: 200000000 },
      ] }),
    });
  });
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\/watchlist$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        source: "tencent",
        quoted_at: "2026-08-21T10:00:00",
        items: Array.from({ length: 12 }, (_, index) => ({
          id: index + 1,
          stock_code: `${600000 + index}`,
          stock_name: `自选股票${index + 1}`,
          note: "",
          created_at: "2026-08-21T09:00:00",
          current_price: 10 + index,
          change_pct: index % 2 ? -0.5 : 0.8,
          quote_source: "tencent",
          alerts: [],
        })),
      }),
    });
  });
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(user) });
  });

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  const main = page.getByRole("region", { name: "首页中间内容" });
  const rail = page.getByRole("complementary", { name: "首页热榜与自选栏" });
  await expect(main).toBeVisible();
  await expect(rail).toBeVisible();
  await expect(page.getByRole("heading", { name: "市场总览" })).toBeVisible();
  await expect(page.getByRole("button", { name: /上证指数.*000001/ })).toBeVisible();
  const shanghaiIndex = page.getByRole("button", { name: /上证指数/ });
  await expect(shanghaiIndex).toContainText("000001");
  const shenzhenIndex = page.getByRole("button", { name: /深证成指/ });
  await expect(shenzhenIndex).toContainText("399001");
  await expect(page.getByText("市场行情")).toHaveCount(0);
  await expect(page.getByText("AI 分析")).toHaveCount(0);
  const [desktopMainBox, desktopRailBox] = await Promise.all([main.boundingBox(), rail.boundingBox()]);
  expect(desktopMainBox).not.toBeNull();
  expect(desktopRailBox).not.toBeNull();
  expect(desktopMainBox!.x + desktopMainBox!.width).toBeLessThan(desktopRailBox!.x);
  await expect(page.getByText("12 只")).toBeVisible();
  await expect(page.getByText(/腾讯行情 · 10:00/)).toBeVisible();
  await expect(page.locator(".dashboard-watchlist-card .ant-card-head")).toHaveCount(0);
  const firstWatchItem = page.locator(".dashboard-watchlist__item").first();
  await expect(firstWatchItem).toHaveClass(/is-up/);
  await expect(page.locator(".dashboard-watchlist__item").nth(1)).toHaveClass(/is-down/);
  await expect(page.getByRole("link", { name: "自选股票1 600000" })).toHaveAttribute("href", "/stock/600000");
  const firstActions = firstWatchItem.locator(".dashboard-watchlist__actions--overlay");
  await expect(firstActions).toHaveCSS("opacity", "0");
  await firstWatchItem.hover();
  await expect(firstActions).toHaveCSS("opacity", "1");
  await expect(page.getByRole("button", { name: "设置自选股票1提醒" })).toBeVisible();
  const scrollMetrics = await page.locator(".dashboard-watchlist__scroll").evaluate((element) => ({
    clientHeight: element.clientHeight,
    scrollHeight: element.scrollHeight,
  }));
  expect(scrollMetrics.scrollHeight).toBeGreaterThan(scrollMetrics.clientHeight);

  await page.setViewportSize({ width: 1100, height: 900 });
  const [compactMainBox, compactRailBox] = await Promise.all([main.boundingBox(), rail.boundingBox()]);
  expect(compactMainBox).not.toBeNull();
  expect(compactRailBox).not.toBeNull();
  expect(compactRailBox!.y).toBeGreaterThan(compactMainBox!.y + compactMainBox!.height);

  await page.setViewportSize({ width: 390, height: 844 });
  const [mobileMainBox, mobileRailBox] = await Promise.all([main.boundingBox(), rail.boundingBox()]);
  expect(mobileMainBox).not.toBeNull();
  expect(mobileRailBox).not.toBeNull();
  expect(mobileRailBox!.y).toBeGreaterThan(mobileMainBox!.y + mobileMainBox!.height);
  await expect(firstActions).toHaveCSS("opacity", "1");
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});
