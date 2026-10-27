import { expect, test, type Page } from "@playwright/test";

const user = {
  id: 7,
  username: "quant-tester",
  is_admin: false,
  must_change_password: false,
};

const draft = {
  id: "draft-one",
  created_by: 7,
  prompt: "生成一个双均线策略",
  definition_hash: `sha256:${"a".repeat(64)}`,
  status: "backtested",
  definition: {
    api_version: "quant.strategy/v1",
    key: "generated_ma_cross",
    version: "1.0.0",
    enabled: true,
    name: "在线双均线",
    description: "短期均线上穿长期均线时入场，下穿时退出",
    scenario: "趋势行情",
    risk_level: "medium",
    parameters: {},
    constraints: [],
    indicators: {},
    signals: {
      entry: { operator: "greater_than", left: "close", right: 0, operands: [] },
      exit: { operator: "less_than", left: "close", right: 0, operands: [] },
    },
  },
  validation: { valid: true, definition_hash: `sha256:${"a".repeat(64)}`, warnings: [] },
  quality_gate: {
    passed: true,
    run_status: "succeeded",
    definition_hash: `sha256:${"a".repeat(64)}`,
    minimum_trade_count: 1,
    maximum_drawdown_pct: 80,
    minimum_sharpe_ratio: 0.5,
    minimum_holdout_trade_count: 2,
    maximum_holdout_drawdown_pct: 20,
    minimum_holdout_sharpe_ratio: 0.2,
    trade_count: 4,
    max_drawdown: -12,
    sharpe_ratio: 1.1,
    holdout_trade_count: 2,
    holdout_max_drawdown: -8,
    holdout_sharpe_ratio: 0.7,
    errors: [],
  },
  created_at: 1,
  updated_at: 2,
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
    model_assumptions: ["信号按 T 日收盘计算，T+1 开盘尝试成交。", "采用前复权行情，不含完整分红送转资金账本。", "停牌、跌停和流动性不足可能延迟退出。"],
    engine_version: "v1",
    data_hash: "hash",
    data_sources: ["tencent"],
    codes: ["600519"],
    metrics: {
      observation_count: 120,
      closed_trade_count: 4,
      total_return: 12.34,
      annualized_return: 11.2,
      annualized_volatility: 10,
      benchmark_return: 8,
      calmar_ratio: 2.15,
      downside_volatility: 7.5,
      excess_return: 4.34,
      information_ratio: 0.72,
      max_drawdown: -5.2,
      profit_loss_ratio: 1.8,
      sharpe_ratio: 1.1,
      sortino_ratio: 1.46,
      tracking_error: 6.03,
      turnover_rate: 100,
      trade_count: 1,
      win_rate: 60,
    },
    equity_curve: [],
    monthly_returns: [],
    trades: [],
    holdout_validation: {
      method: "holdout",
      start_date: "2025-09-01",
      end_date: "2025-12-31",
      training_ratio: 2 / 3,
      observation_count: 20,
      metrics: {
        total_return: 3.4,
        annualized_return: 9.2,
        annualized_volatility: 11,
        benchmark_return: 2.5,
        calmar_ratio: 1.7,
        downside_volatility: 6.8,
        excess_return: 0.9,
        information_ratio: 0.4,
        max_drawdown: -2,
        profit_loss_ratio: 1.4,
        sharpe_ratio: 0.8,
        sortino_ratio: 1.2,
        tracking_error: 4,
        turnover_rate: 30,
        trade_count: 2,
        win_rate: 50,
      },
    },
  },
};

async function mockQuantApi(page: Page, options: { isAdmin?: boolean } = {}) {
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\//, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ...user, is_admin: options.isAdmin ?? false }),
    });
  });
  await page.route("**/api/quant/strategy-presets", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\/quant\/strategies$/, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\/quant\/backtests(?:\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [run] }),
    });
  });
  await page.route("**/api/quant/backtests/run-one", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(run) });
  });
  await page.route("**/api/quant/strategy-registry", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ generation: 3, published_directory: "/data/quant-strategies-published" }),
    });
  });
  await page.route("**/api/quant/strategy-drafts", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([draft]) });
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
  await expect(page.getByText("索提诺比率").first()).toBeVisible();
  await expect(page.getByText("信息比率").first()).toBeVisible();
  await expect(page.getByText("下行波动")).toBeVisible();
  await expect(page.getByText("跟踪误差")).toBeVisible();
  await expect(page.getByText("后段样本验证")).toBeVisible();
  await expect(page.getByText("独立资金")).toBeVisible();

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

test("shows full-sample and holdout gates in the strategy authoring workspace", async ({ page }) => {
  await mockQuantApi(page, { isAdmin: true });
  await page.goto("/quant?view=authoring");

  await expect(page.getByRole("region", { name: "在线策略生成工作台" })).toBeVisible();
  await expect(page.getByText(/全样本：交易 4 次/)).toContainText("夏普 1.1");
  await expect(page.getByText(/后段样本：交易 2 次/)).toContainText("最大回撤 -8%");
  await expect(page.getByRole("spinbutton", { name: "整体最低夏普比率（可选）" })).toBeVisible();
  await expect(page.getByRole("spinbutton", { name: "后段最低交易次数（可选）" })).toBeVisible();
  await expect(page.getByRole("spinbutton", { name: "后段最大允许回撤（可选，%）" })).toBeVisible();
  await expect(page.getByRole("spinbutton", { name: "后段最低夏普比率（可选）" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});

for (const { width, theme } of [
  { width: 1440, theme: "stellar-blue" },
  { width: 1440, theme: "light" },
  { width: 1024, theme: "light" },
  { width: 390, theme: "stellar-blue" },
  { width: 360, theme: "light" },
]) {
  test(`keeps quant settings and metrics readable at ${width}px in ${theme}`, async ({ page }, testInfo) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setViewportSize({ width, height: 960 });
    await page.addInitScript((themeKey) => {
      localStorage.setItem("a-share-agent-theme", JSON.stringify({ state: { themeKey }, version: 0 }));
    }, theme);
    await mockQuantApi(page);
    await page.goto("/quant");
    await expect(page.getByLabel("回测类型")).toContainText("日线回测");
    await page.getByRole("button", { name: /高级执行参数/ }).click();
    for (const name of ["交易成本", "仓位管理", "退出保护"]) {
      await expect(page.getByRole("region", { name, exact: true })).toBeVisible();
    }
    const execution = page.getByRole("region", { name: /3\. 执行设置/ });
    const strategyBox = await page.locator(".quant-strategy-stage").boundingBox();
    const universeBox = await page.locator(".quant-form-layout__universe").boundingBox();
    const executionBox = await execution.boundingBox();
    expect(executionBox!.y).toBeGreaterThanOrEqual(strategyBox!.y + strategyBox!.height);
    expect(executionBox!.y).toBeGreaterThanOrEqual(universeBox!.y + universeBox!.height);
    if (width >= 1200) {
      expect(executionBox!.width).toBeGreaterThan(strategyBox!.width);
    }
    await expect(page.getByLabel("印花税（BP）", { exact: true })).toBeEnabled();
    const feeMode = page.getByRole("combobox", { name: /^税费模式/ });
    await feeMode.click();
    await page.getByText("A 股历史税率", { exact: true }).click();
    await expect(page.getByLabel("印花税（BP）", { exact: true })).toBeDisabled();
    await expect(page.getByLabel("过户费（BP）", { exact: true })).toBeDisabled();
    await expect(page.getByLabel("佣金（BP）", { exact: true })).toBeEnabled();
    await feeMode.click();
    await page.getByText("自定义固定税率", { exact: true }).click();
    await expect(page.getByLabel("印花税（BP）", { exact: true })).toBeEnabled();

    const stopLoss = page.getByRole("spinbutton", { name: /^持仓止损/ });
    await stopLoss.fill("8");
    await page.getByRole("button", { name: /高级执行参数/ }).click();
    await expect(page.getByRole("region", { name: "退出保护", exact: true })).toBeHidden();
    await page.getByRole("button", { name: /高级执行参数/ }).click();
    await expect(stopLoss).toHaveValue("8");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    expect(await execution.evaluate((el) => el.scrollWidth <= el.clientWidth + 1)).toBe(true);
    if (process.env.QUANT_UI_SCREENSHOTS) {
      await execution.screenshot({ path: testInfo.outputPath("execution.png") });
      await page.evaluate(() => window.scrollTo(0, 0));
      await page.screenshot({ path: testInfo.outputPath("setup.png"), fullPage: true });
    }

    await page.goto("/quant?panel=result&run=run-one");
    const core = page.getByRole("group", { name: "核心回测指标" });
    await expect(core).toBeVisible();
    await expect(core.locator(".quant-metric-card")).toHaveCount(4);
    await expect(core.getByText("交易日样本数")).toBeVisible();
    await expect(core).toContainText("120");
    await expect(page.getByRole("group", { name: "补充回测指标" }).locator(".quant-metric-card")).toHaveCount(6);
    const assumptions = page.getByRole("complementary", { name: "回测模型与适用边界" });
    await expect(assumptions).toContainText("历史表现不代表未来收益");
    await expect(assumptions.locator("ul")).toBeHidden();
    await assumptions.locator("summary").click();
    await expect(assumptions.locator("ul")).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
    if (process.env.QUANT_UI_SCREENSHOTS) {
      await page.screenshot({ path: testInfo.outputPath("result.png"), fullPage: true });
    }
    expect(errors).toEqual([]);
  });
}
