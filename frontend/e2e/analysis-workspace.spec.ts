import { expect, test, type Page } from "@playwright/test";

const user = {
  id: 7,
  username: "researcher",
  is_admin: false,
  must_change_password: false,
};

const analysisResult = {
  stock_code: "600519",
  stock_name: "贵州茅台",
  analysis_date: "2026-08-20",
  current_price: 1520,
  fundamental: {
    score: 8.2,
    summary: "盈利质量稳定",
    strengths: ["品牌壁垒稳固"],
    risks: ["估值仍处高位"],
  },
  technical: {
    score: 7.1,
    summary: "趋势处于确认阶段",
    strengths: ["中期均线向上"],
    risks: ["短期量能不足"],
    support_level: 1450,
    resistance_level: 1650,
    trend: "中期上行",
    key_signals: ["均线多头排列", "量价配合改善"],
  },
  sentiment: {
    score: 6.8,
    summary: "情绪温和偏多",
    strengths: ["机构关注稳定"],
    risks: ["市场分歧仍存"],
    market_mood: "温和偏多，机构关注稳定但短线分歧仍在",
  },
  valuation_view: "合理偏高",
  fair_value_range: [1450, 1650],
  blended_fair_value: 1560,
  overall_rating: 7.6,
  overall_summary: "基本面稳健，但应等待关键支撑确认。",
  estimated_price_range: [1480, 1680],
  signal: "buy",
  confidence: 0.82,
  key_factors: ["盈利韧性", "渠道质量"],
  risk_warnings: ["消费复苏不及预期", "估值回撤"],
};

async function mockAnalysisApi(page: Page, valuationMethods: Record<string, unknown> = {}) {
  const watchlistWrites: unknown[] = [];
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\//, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(user) });
  });
  const pageData = {
        stock_info: {
          code: "600519",
          name: "贵州茅台",
          listing_date: "2001-08-27",
          total_shares: 1_256_197_800,
          circulating_shares: 1_256_197_800,
          pe_ttm: 23.1,
          pe_static: 24.2,
          pb: 7.8,
          market_cap: 1_909_420_000_000,
          float_market_cap: 1_909_420_000_000,
          turnover_pct: 0.31,
          exchange_industry: "酒、饮料和精制茶制造业",
          first_industry: { code: "801120", name: "食品饮料" },
          second_industry: { code: "801125", name: "白酒Ⅱ" },
          current_price: 1520,
          concepts: [],
        },
        kline: {
          code: "600519",
          period: "daily",
          adjust: "qfq",
          source: "mock",
          adjustment_verified: true,
          items: [
            { date: "2026-08-19", open: 1500, close: 1510, high: 1522, low: 1498, volume: 1200, amount: 1_812_000, amplitude: 1.6, turnover_pct: 0.2, change_pct: 0.67 },
            { date: "2026-08-20", open: 1512, close: 1520, high: 1528, low: 1508, volume: 1350, amount: 2_052_000, amplitude: 1.32, turnover_pct: 0.22, change_pct: 0.66 },
          ],
        },
        intraday: {
          code: "600519",
          prev_close: 1510,
          items: [
            { time: "09:30", price: 1512, avg_price: 1512, volume: 100, amount: 151_200, change_pct: 0.13 },
            { time: "10:00", price: 1535.2, avg_price: 1516, volume: 180, amount: 276_336, change_pct: 1.67 },
          ],
        },
        valuation: { code: "600519", pe_ttm: 23.1, pb: 7.8, ps_ttm: 9.2, peers: [] },
        cached_analysis: analysisResult,
        partial: false,
        unavailable_sections: [],
      };
  await page.route("**/api/stock/600519/info", async (route) => {
    await route.fulfill({ json: pageData.stock_info });
  });
  await page.route("**/api/stock/600519/intraday", async (route) => {
    await route.fulfill({ json: pageData.intraday });
  });
  await page.route("**/api/stock/analysis-page/600519?include_market_data=false", async (route) => {
    await route.fulfill({ json: { cached_analysis: pageData.cached_analysis, partial: false, unavailable_sections: [] } });
  });
  await page.route("**/api/stock/600519/financial?**", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/stock/600519/valuation-detail", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: "600519", report_date: "2026-06-30", current_price: 1520, market_cap: 1_909_420_000_000, total_shares: 1_256_197_800, industry: "白酒",
        multiples: { pe_ttm: 23.1, pb: 7.8, ps_ttm: 9.2, peg: 1.5 },
        percentiles: { pe_3y: 45, pb_3y: 52, ps_3y: 48 },
        fundamentals: { revenue: 100, revenue_yoy: 8, net_profit: 50, net_profit_yoy: 9, non_net_profit: 48, non_net_profit_yoy: 8, shareholders_equity: 200, operating_cashflow: 55 },
        peer_summary: {
          pe_median: 20, pb_median: 5, ps_median: 7, peer_count: 0, peers: [],
          pe_stats: { sample_size: 0, excluded_count: 0, confidence_score: 0 },
          pb_stats: { sample_size: 0, excluded_count: 0, confidence_score: 0 },
          ps_stats: { sample_size: 0, excluded_count: 0, confidence_score: 0 },
        },
        fair_values: valuationMethods, blended_fair_value: 1560, fair_value_range: [1450, 1650], valuation_view: "合理偏高", valuation_summary: "估值处于历史中位偏上",
        profile: { category: "quality", label: "高质量龙头", rationale: [] }, method_weights: {}, notes: [], institution_forecasts: [],
      }),
    });
  });
  await page.route("**/api/stock/600519/news-categorized", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ cls_news: [], eastmoney_news: [] }) });
  });
  await page.route("**/api/stock/600519/sentiment", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ heat_score: 68, hot_rank: 15 }) });
  });
  await page.route("**/api/stock/600519/retail-sentiment", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ score: 62, guba_post_count: 0, post_count: 0, bullish_ratio: 0.6, summary: "讨论情绪温和", sample_posts: [] }) });
  });
  await page.route("**/api/stock/600519/indicators", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        ma: { ma5: 1510, ma10: 1490, ma20: 1470, ma60: 1410 },
        macd: { dif: 12.4, dea: 10.8, macd_hist: 3.2 },
        rsi: 61.5,
        boll: { upper: 1560, middle: 1490, lower: 1420 },
        kdj: { k: 68, d: 62, j: 80 },
        volume_ma: { ma5: 120000, ma10: 110000 },
        series: { dates: [], ma5: [], ma10: [], ma20: [], ma60: [], dif: [], dea: [], macd_hist: [], rsi: [], boll_upper: [], boll_middle: [], boll_lower: [], k: [], d: [], j: [], volume_ma5: [], volume_ma10: [] },
      }),
    });
  });
  await page.route("**/api/analysis/600519/history/20260820", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(analysisResult),
    });
  });
  await page.route("**/api/analysis/history/all?**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          stock_code: "600519",
          stock_name: "贵州茅台",
          analysis_date: "2026-08-20",
          current_price: 1520,
          overall_rating: 7.6,
          signal: "buy",
          confidence: 0.82,
          can_delete: true,
        },
        {
          stock_code: "300750",
          stock_name: "宁德时代",
          analysis_date: "2026-08-19",
          current_price: 283,
          overall_rating: 6.9,
          signal: "hold",
          confidence: 0.74,
          can_delete: true,
        },
      ]),
    });
  });
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\/watchlist$/, async (route) => {
    if (route.request().method() === "POST") {
      watchlistWrites.push(route.request().postDataJSON());
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ id: 1, stock_code: "600519", stock_name: "贵州茅台", note: "来自分析工作台" }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ source: "mock", quoted_at: "2026-08-20T15:00:00+08:00", items: [] }),
    });
  });
  return { watchlistWrites };
}

type GeometryBox = { x: number; y: number; width: number; height: number };

function boxesIntersect(left: GeometryBox, right: GeometryBox, tolerance = 1) {
  const overlapWidth = Math.min(left.x + left.width, right.x + right.width) - Math.max(left.x, right.x);
  const overlapHeight = Math.min(left.y + left.height, right.y + right.height) - Math.max(left.y, right.y);
  return overlapWidth > tolerance && overlapHeight > tolerance;
}

async function expectAnalysisGeometry(page: Page) {
  const stockHeaderBox = await page.locator(".analysis-workspace__header .analysis-header-card").boundingBox();
  expect(stockHeaderBox).not.toBeNull();
  const alignedSurfaces = page.locator(
    ".analysis-workspace__result > .ant-card",
  );
  expect(await alignedSurfaces.count()).toBe(1);
  for (let index = 0; index < await alignedSurfaces.count(); index += 1) {
    const surfaceBox = await alignedSurfaces.nth(index).boundingBox();
    expect(surfaceBox).not.toBeNull();
    expect(Math.abs(stockHeaderBox!.x - surfaceBox!.x)).toBeLessThanOrEqual(2);
    expect(Math.abs(
      stockHeaderBox!.x + stockHeaderBox!.width - surfaceBox!.x - surfaceBox!.width,
    )).toBeLessThanOrEqual(2);
  }

  const surfaceLocator = page.locator([
    ".analysis-workspace__history",
    ".analysis-workspace__header > .analysis-header-card",
    ".analysis-workspace__main > .ant-card",
    ".analysis-workspace__main > .u-card",
    ".analysis-charts-section > .ant-card",
    ".analysis-workspace__result > .ant-card",
  ].join(","));
  const surfaces = (await Promise.all(
    Array.from({ length: await surfaceLocator.count() }, (_, index) => surfaceLocator.nth(index).boundingBox()),
  )).filter((box): box is GeometryBox => box !== null);

  for (let leftIndex = 0; leftIndex < surfaces.length; leftIndex += 1) {
    for (let rightIndex = leftIndex + 1; rightIndex < surfaces.length; rightIndex += 1) {
      expect(boxesIntersect(surfaces[leftIndex], surfaces[rightIndex])).toBe(false);
    }
  }

  await expect(page.locator(".analysis-charts-section, .analysis-kline-card")).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
}

test("renders the desktop terminal command frame without a standalone context rail", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const { watchlistWrites } = await mockAnalysisApi(page);
  await page.goto("/analysis/600519");

  await expect(page.getByRole("navigation", { name: "全局快捷操作" })).toHaveCount(0);
  expect(await page.locator("html").getAttribute("data-theme")).toBe("stellar-blue");
  await expect(page.getByRole("button", { name: /数据源/ })).toHaveCount(0);
  await expect(page.getByRole("complementary", { name: "最近分析记录" })).toBeVisible();
  await expect(page.getByRole("complementary", { name: "分析上下文" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "分析上下文" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "决策重点与 AI 追问" })).toContainText("等待关键支撑确认后再评估");
  await page.screenshot({ path: "/tmp/analysis-desktop.png", fullPage: true });

  const historyBox = await page.getByRole("complementary", { name: "最近分析记录" }).boundingBox();
  const decisionBox = await page.getByRole("region", { name: "决策重点与 AI 追问" }).boundingBox();
  expect(historyBox).not.toBeNull();
  expect(historyBox!.width).toBeLessThanOrEqual(180);
  const analysisPageBox = await page.locator(".analysis-page").boundingBox();
  expect(analysisPageBox).not.toBeNull();
  // The page container owns a 4px focus/layout inset; what matters is that the
  // history rail remains left of, and does not overlap, the decision content.
  expect(historyBox!.x).toBeGreaterThanOrEqual(analysisPageBox!.x);
  expect(decisionBox).not.toBeNull();
  expect(historyBox!.x + historyBox!.width).toBeLessThan(decisionBox!.x);
  await expect(page.locator(".analysis-sentiment-gauge")).toHaveCount(0);

  const valuationBox = await page.locator(".analysis-conclusion__metrics").boundingBox();
  const factorSectionBox = await page.locator(".analysis-conclusion__decision-grid").boundingBox();
  expect(valuationBox).not.toBeNull();
  expect(factorSectionBox).not.toBeNull();
  expect(factorSectionBox!.y - valuationBox!.y - valuationBox!.height).toBeGreaterThanOrEqual(16);

  const stockCode = page.locator(".analysis-header-card").getByText("600519", { exact: true });
  await expect(page.locator(".analysis-header-card").getByText("¥1535.20", { exact: true })).toBeVisible();
  const watchlistButton = page.getByRole("button", { name: "加入自选" });
  expect(await stockCode.evaluate((element) => element.parentElement?.contains(
    document.querySelector('[aria-label="加入自选"]'),
  ))).toBe(true);

  const conclusionCards = page.locator(
    ".analysis-conclusion__score-panel, .analysis-conclusion__factor-card",
  );
  const conclusionBoxes = (await Promise.all(
    Array.from({ length: await conclusionCards.count() }, (_, index) => conclusionCards.nth(index).boundingBox()),
  )).filter((box): box is GeometryBox => box !== null);
  expect(conclusionBoxes).toHaveLength(3);
  expect(Math.max(...conclusionBoxes.map((box) => box.y)) - Math.min(...conclusionBoxes.map((box) => box.y))).toBeLessThanOrEqual(2);
  for (let leftIndex = 0; leftIndex < conclusionBoxes.length; leftIndex += 1) {
    for (let rightIndex = leftIndex + 1; rightIndex < conclusionBoxes.length; rightIndex += 1) {
      expect(boxesIntersect(conclusionBoxes[leftIndex], conclusionBoxes[rightIndex])).toBe(false);
    }
  }
  await expect(watchlistButton).toBeVisible();
  await expectAnalysisGeometry(page);
  await expect(page.locator(".analysis-page")).toHaveCSS("container-type", "inline-size");
  await expect.poll(() => page.locator(".analysis-conclusion").evaluate(
    (element) => Boolean(element.closest(".analysis-research-conclusion")),
  )).toBe(true);

  await page.getByRole("button", { name: "加入自选" }).click();
  await expect.poll(() => watchlistWrites).toEqual([{ stock_code: "600519", note: "来自分析工作台" }]);
  await expect(page.getByText("已加入自选")).toBeVisible();

  await page.getByRole("button", { name: /失效条件/ }).click();
  await expect(page).toHaveURL(/\/chat\?prompt=/);
  expect(decodeURIComponent(page.url())).toContain("贵州茅台当前结论的失效条件是什么");
});

test("shows research results without technical dimensions or an empty panel", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mockAnalysisApi(page);
  const requests: string[] = [];
  page.on("request", (request) => requests.push(request.url()));
  await page.goto("/analysis/600519?panel=technical");
  await expect(page.getByRole("region", { name: "个股分析结果", exact: true })).toBeVisible();
  await expect(page.getByRole("tab", { name: "技术面", exact: true })).toHaveCount(0);
  await expect(page.getByText("技术面", { exact: true })).toHaveCount(0);
  await expect(page.getByRole("combobox", { name: "个股研究维度" })).toHaveCount(0);
  await expect(page.locator(".analysis-panels-card, #analysis-details")).toHaveCount(0);
  expect(requests.some((url) => /TechnicalPanel|\/(indicators|kline|chip-distribution)(?:\?|$)/.test(url))).toBe(false);
  await expectAnalysisGeometry(page);
});

test("loads a historical snapshot without the informational banner", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mockAnalysisApi(page);
  await page.goto("/analysis/600519?date=20260820");

  await expect(page.getByRole("heading", { name: "综合研判" })).toBeVisible();
  await expect(page.getByText("正在查看 2026-08-20 的历史分析快照")).toHaveCount(0);
  await expect(page.getByText("AI 结论与评分保持为当日结果")).toHaveCount(0);
});

test("keeps the mobile workspace ordered without horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockAnalysisApi(page);
  await page.goto("/analysis/600519");

  await expect(page.getByRole("button", { name: "打开导航菜单" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "全局快捷操作" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "决策重点与 AI 追问" })).toBeVisible();
  await page.screenshot({ path: "/tmp/analysis-mobile.png", fullPage: true });

  const decisionBox = await page.getByRole("region", { name: "决策重点与 AI 追问" }).boundingBox();
  const historyBox = await page.getByRole("complementary", { name: "最近分析记录" }).boundingBox();
  expect(decisionBox).not.toBeNull();
  expect(historyBox).not.toBeNull();
  expect(historyBox!.y).toBeLessThan(decisionBox!.y);
  await expectAnalysisGeometry(page);
});

test("keeps the 1180px desktop grid aligned without overlapping cards", async ({ page }) => {
  await page.setViewportSize({ width: 1180, height: 900 });
  await mockAnalysisApi(page);
  await page.goto("/analysis/600519");

  const historyBox = await page.locator(".analysis-workspace__history").boundingBox();
  const headerBox = await page.locator(".analysis-workspace__header").boundingBox();
  expect(historyBox).not.toBeNull();
  expect(headerBox).not.toBeNull();
  expect(historyBox!.x + historyBox!.width).toBeLessThanOrEqual(headerBox!.x - 1);
  await expectAnalysisGeometry(page);
});

for (const width of [1920, 1180, 390]) {
  test(`shows the result directly below analysis state at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mockAnalysisApi(page);
    await page.goto("/analysis/600519?panel=research");

    const result = page.getByRole("region", { name: "个股分析结果", exact: true });
    await expect(result.getByRole("tab", { name: "研究结论" })).toBeVisible();
    await expect(result.getByRole("heading", { name: "综合研判" })).toBeVisible();
    await expect(page.locator(".analysis-panels-card, .analysis-workspace__details")).toHaveCount(0);
    await expect(page.locator(".analysis-workspace > :last-child")).toHaveClass("analysis-workspace__result");

    const expectBottomResult = async () => {
      // Read in one frame so chart loading or sticky positioning cannot skew comparisons.
      await expect.poll(() => page.evaluate(() => {
        const resultBox = document.querySelector(".analysis-workspace__result")!.getBoundingClientRect();
        const detailsBox = document.querySelector(".analysis-workspace__main")!.getBoundingClientRect();
        return resultBox.top >= detailsBox.bottom - 1
          && Math.abs(resultBox.left - detailsBox.left) <= 2
          && Math.abs(resultBox.width - detailsBox.width) <= 2;
      })).toBe(true);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    };
    await expectBottomResult();
    const layout = await result.evaluate((element) => {
      const overview = element.querySelector(".analysis-conclusion")!.getBoundingClientRect();
      const actions = element.querySelector(".analysis-decision-board")!.getBoundingClientRect();
      return { isBeside: actions.left >= overview.right - 1, isBelow: actions.top >= overview.bottom - 1 };
    });
    expect(width === 1920 ? layout.isBeside : layout.isBelow).toBe(true);
    await expect(result.getByText("分析日期 2026-08-20")).toBeVisible();
    await page.getByRole("link", { name: "查看结论", exact: true }).click();
    await expect(page).toHaveURL(/#analysis-result$/);
    await expect(result.getByRole("tab", { name: "研究结论" })).toBeInViewport();
    await expect(result.getByRole("link", { name: /返回研究维度/ })).toHaveCount(0);
    await expect(result.getByRole("link", { name: /查看个股资料/ })).toHaveAttribute("href", "/stock/600519");
    await result.evaluate((element) => element.scrollIntoView({ block: "start" }));
    await page.screenshot({ path: `/tmp/analysis-result-bottom-${width}.png` });
  });
}

for (const width of [1920, 390]) {
  test(`shares stock data and keeps Chanlun on the stock page at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mockAnalysisApi(page);
    const requests: string[] = [];
    const pageErrors: string[] = [];
    page.on("request", (request) => {
      const url = new URL(request.url());
      if (url.pathname.startsWith("/api/stock/")) requests.push(url.pathname + url.search);
    });
    page.on("pageerror", (error) => pageErrors.push(error.message));
    await page.route("**/api/stock/600519/business-intro", (route) => route.fulfill({ json: { code: "600519", main_business: "白酒生产" } }));
    await page.route("**/api/stock/600519/kline?**", (route) => route.fulfill({ json: {
      code: "600519", period: "daily", items: Array.from({ length: 60 }, (_, i) => {
        const price = 1520 + Math.sin(i / 3) * 60;
        return { date: new Date(Date.UTC(2026, 5, 1 + i)).toISOString().slice(0, 10), open: price, close: price + 5, high: price + 10, low: price - 10, volume: 1000, amount: price * 1000 };
      }),
    } }));
    await page.goto("/stock/600519");
    const toggle = page.getByRole("switch", { name: "缠论" });
    await expect(toggle).not.toBeChecked();
    await page.locator("#stock-charts").evaluate((element) => element.scrollIntoView({ block: "start" }));
    await expect(page.locator("#stock-charts canvas").first()).toBeAttached();
    await toggle.click();
    await expect(toggle).toBeChecked();
    await page.getByText("周K", { exact: true }).click();
    // 切换周期后周 K 请求次数必须稳定下来，而不是持续增长。
    // 不能断言“恰好 1 次”：CI 的 E2E 跑 dev server，React StrictMode 会双调用 effect，
    // 且首屏可能在 StrictMode 卸载重挂前已发过一次。这里真正要防的是
    // “向左回溯历史”与左缘回调形成的无界循环（曾观测到同一周期被打 10 次）。
    const weeklyRequestCount = () =>
      requests.filter((url) => url.includes("/kline?") && url.includes("period=weekly")).length;
    await expect.poll(weeklyRequestCount, { timeout: 10_000 }).toBeGreaterThan(0);
    const settled = await weeklyRequestCount();
    await page.waitForTimeout(1_500);
    expect(weeklyRequestCount()).toBe(settled);
    await expect(page.locator("#stock-charts canvas").first()).toBeAttached();
    const chartLayout = await page.locator("#stock-charts").evaluate((element) => {
      const toolbar = element.querySelector(".stock-chart-toolbar")!.getBoundingClientRect();
      const hud = element.querySelector(".kline-chart__hud")!;
      const hudRect = hud.getBoundingClientRect();
      const plot = element.querySelector(".kline-chart__plot")!.getBoundingClientRect();
      return {
        toolbarBottom: toolbar.bottom,
        hudTop: hudRect.top,
        hudBottom: hudRect.bottom,
        plotTop: plot.top,
        quotesTop: hud.firstElementChild!.getBoundingClientRect().top,
        quotesBottom: hud.firstElementChild!.getBoundingClientRect().bottom,
      };
    });
    expect(chartLayout.hudTop).toBeGreaterThanOrEqual(chartLayout.toolbarBottom - 1);
    expect(chartLayout.quotesTop).toBeGreaterThanOrEqual(chartLayout.hudTop);
    expect(chartLayout.quotesBottom).toBeLessThanOrEqual(chartLayout.hudBottom);
    expect(chartLayout.plotTop).toBeGreaterThanOrEqual(chartLayout.hudBottom - 1);
    await page.getByText("后复权", { exact: true }).click();
    await expect.poll(() => requests.filter((url) => url.includes("/kline?") && url.includes("adjust=hfq")).length).toBe(1);
    await toggle.click();
    await expect(toggle).not.toBeChecked();
    const beforeAnalysis = requests.length;
    await page.getByRole("button", { name: "进入 AI 分析" }).click();
    await expect(page.getByRole("region", { name: "个股分析结果", exact: true })).toBeVisible();
    await expect(page.getByRole("tab", { name: "技术面", exact: true })).toHaveCount(0);
    await expect(page.getByRole("region", { name: "技术面详情" })).toHaveCount(0);
    await expectAnalysisGeometry(page);
    await expect(page.locator(".analysis-charts-section, .analysis-kline-card")).toHaveCount(0);
    await expect(page.getByRole("switch", { name: "缠论" })).toHaveCount(0);
    await expect(page.getByText("RSI", { exact: true })).toHaveCount(0);
    await expect(page.locator(".analysis-header-card__metrics").getByText("¥1535.20", { exact: true })).toHaveText("¥1535.20");
    expect(requests.filter((url) => url === "/api/stock/600519/info")).toHaveLength(1);
    expect(requests.filter((url) => url === "/api/stock/600519/intraday")).toHaveLength(1);
    expect(requests.slice(beforeAnalysis).some((url) => /\/(kline|indicators|chip-distribution|valuation)(?:\?|$)/.test(url))).toBe(false);
    expect(requests).toContain("/api/stock/analysis-page/600519?include_market_data=false");
    await page.getByRole("navigation", { name: "个股页面" }).getByRole("link", { name: "个股资料", exact: true }).click();
    await expect(page).toHaveURL(/\/stock\/600519$/);
    await page.locator("#stock-charts").scrollIntoViewIfNeeded();
    await expect(page.getByRole("switch", { name: "缠论" })).toBeInViewport();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    expect(pageErrors).toEqual([]);
  });
}

for (const width of [1440, 390]) {
  test(`moves fundamentals and retail comments to profile tabs at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mockAnalysisApi(page);
    const requests: string[] = [];
    const errors: string[] = [];
    page.on("request", (request) => {
      if (request.url().includes("/api/stock/")) requests.push(request.url());
    });
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route("**/api/stock/600519/revenue-breakdown", (route) => route.fulfill({ json: {
      code: "600519", source: "sina", amount_unit: "CNY_yuan", by_product: [{
        id: "1", class_name: "茅台酒", is_sub_item: false, revenue: 100000000, cost: 10000000,
        gross_profit: 90000000, revenue_share_pct: 90, gross_margin_pct: 90,
      }], by_business: [], by_region: [],
    } }));
    await page.route("**/api/stock/600519/retail-sentiment", (route) => route.fulfill({ json: {
      score: 62, guba_post_count: 1, post_count: 1, bullish_ratio: 0.6, summary: "讨论情绪温和",
      sample_posts: [{ text: "看好长期品牌价值", author: "投资者", publish_time: "2026-09-24 10:00" }],
    } }));
    await page.goto("/stock/600519");
    await page.locator(".stock-deferred-section").scrollIntoViewIfNeeded();
    await expect(page.getByRole("tab", { name: "财务", exact: true })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("region", { name: "基本面概览" })).toBeVisible();
    await expect(page.getByText("盈利质量稳定", { exact: true })).toBeVisible();
    await expect(page.getByTestId("revenue-breakdown-interactive").getByText("茅台酒", { exact: true })).toBeVisible();
    await expect(page.getByText("关键财务指标", { exact: true })).toBeVisible();
    expect(requests.some((url) => url.includes("/retail-sentiment"))).toBe(false);
    const layout = await page.getByRole("region", { name: "基本面概览" }).evaluate((element) => {
      const score = element.querySelector(".analysis-dimension-summary__score")!.getBoundingClientRect();
      const content = element.querySelector(".analysis-dimension-summary__content")!.getBoundingClientRect();
      return { beside: content.left >= score.right - 1, below: content.top >= score.bottom - 1 };
    });
    expect(width > 767 ? layout.beside : layout.below).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    await page.locator(".stock-detail-tabs").screenshot({ path: `/tmp/stock-financial-tabs-${width}.png` });

    await page.getByRole("tab", { name: "资讯", exact: true }).click();
    await page.getByRole("tab", { name: "散户评论", exact: true }).click();
    await expect(page.getByText("看好长期品牌价值", { exact: true })).toBeVisible();
    await expect(page.getByText("60.0%", { exact: true })).toBeVisible();
    await expect(page).toHaveURL(/tab=information/);
    await page.locator(".stock-detail-tabs").screenshot({ path: `/tmp/stock-comments-tabs-${width}.png` });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);

    await page.getByRole("link", { name: "AI 分析", exact: true }).click();
    await expect(page.getByRole("region", { name: "个股分析结果", exact: true })).toBeVisible();
    await expect(page.getByRole("region", { name: "基本面概览" })).toHaveCount(0);
    await expect(page.getByText("情绪面", { exact: true })).toHaveCount(0);
    await expect(page.getByRole("tab", { name: "基本面", exact: true })).toHaveCount(0);
    expect(requests.some((url) => /\/sentiment$/.test(url))).toBe(false);
    expect(errors).toEqual([]);
  });
}

for (const width of [1440, 390]) {
  test(`opens the standalone profile valuation tab and redirects old links at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mockAnalysisApi(page);
    const requests: string[] = [];
    const errors: string[] = [];
    page.on("request", (request) => requests.push(request.url()));
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto("/analysis/600519");
    await expect(page.getByRole("region", { name: "个股分析结果", exact: true })).toBeVisible();
    await expect(page.getByRole("tab", { name: "估值面", exact: true })).toHaveCount(0);
    expect(requests.some((url) => url.includes("/valuation-detail"))).toBe(false);

    await page.goto("/analysis/600519?panel=valuation&date=20260820");
    await expect(page).toHaveURL(/\/stock\/600519\?tab=valuation&date=20260820#stock-details$/);
    await expect(page.getByRole("tab", { name: "估值", exact: true })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("heading", { name: "估值分析" })).toBeVisible();
    await expect(page.getByText("五种估值结果", { exact: true })).toBeVisible();
    await expect(page.getByText(/来自 2026-08-20 的历史报告/)).toBeVisible();
    await expect(page.getByRole("heading", { name: "估值分析" })).toBeInViewport();
    expect(requests.some((url) => url.includes("/valuation-detail"))).toBe(true);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    await page.locator("#stock-details").screenshot({ path: `/tmp/stock-valuation-${width}.png` });
    expect(errors).toEqual([]);
  });
}

for (const width of [1440, 1180, 390]) {
  test(`aligns valuation cards without a left score column at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    const common = {
      available: true, confidence_score: 0.85, data_quality_score: 0.9, weight: 0.2,
      per_share_value: 1520, value_range: [1320, 1820], upside_pct: 12.5,
    };
    const longBasis = "结合行业可比公司、盈利能力和资产质量进行综合判断。".repeat(4);
    const reason = "现金流波动较大且缺少完整历史样本，暂无法形成可靠的折现估值。";
    await mockAnalysisApi(page, {
      pe: { ...common, method: "pe", basis: "同行中位数", applicability: "盈利稳定" },
      pb: { ...common, method: "pb", basis: longBasis, applicability: "适合重资产且净资产质量较好的公司" },
      ps: { ...common, method: "ps", per_share_value: 98765.43 },
      peg: { ...common, method: "peg", confidence_score: 1, basis: "成长性与估值匹配", applicability: "使用中期盈利增长预期" },
      dcf: { ...common, method: "dcf", available: false, reason, applicability: "需先核验现金流质量" },
    });
    const errors: string[] = [];
    const requests: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("request", (request) => requests.push(request.url()));
    await page.goto("/stock/600519?tab=valuation#stock-details");
    const snapshot = page.getByRole("region", { name: "当前估值快照" });
    await expect(snapshot).toBeVisible();
    await expect(page.getByText("估值面", { exact: true })).toHaveCount(0);
    await expect(page.locator(".valuation-panel .analysis-dimension-summary__score")).toHaveCount(0);
    const cards = page.locator(".valuation-method-card");
    await expect(cards).toHaveCount(5);
    await expect(page.getByText(longBasis, { exact: true })).toBeVisible();
    await expect(page.getByText(reason, { exact: true })).toBeVisible();
    const boxes = await cards.evaluateAll((elements) => elements.map((element) => {
      const rect = element.getBoundingClientRect();
      const value = element.querySelector(".valuation-method-card__value")!;
      const title = element.querySelector(".valuation-method-card__title")!;
      return {
        width: rect.width, height: rect.height,
        titleTop: title.getBoundingClientRect().top - rect.top,
        valueTop: value.getBoundingClientRect().top - rect.top,
        valueSize: getComputedStyle(value).fontSize,
        titleSize: getComputedStyle(title).fontSize,
        clipped: element.scrollHeight > element.clientHeight + 1 || element.scrollWidth > element.clientWidth + 1,
      };
    }));
    for (const box of boxes) {
      expect(Math.abs(box.width - boxes[0].width)).toBeLessThanOrEqual(1);
      expect(Math.abs(box.height - boxes[0].height)).toBeLessThanOrEqual(1);
      expect(Math.abs(box.titleTop - boxes[0].titleTop)).toBeLessThanOrEqual(1);
      expect(Math.abs(box.valueTop - boxes[0].valueTop)).toBeLessThanOrEqual(1);
      expect(box.valueSize).toBe(boxes[0].valueSize);
      expect(box.titleSize).toBe(boxes[0].titleSize);
      expect(box.clipped).toBe(false);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    expect(requests.some((url) => url.includes("/analysis-page/") || /\/api\/analysis\/.*\/history\//.test(url))).toBe(false);
    expect(errors).toEqual([]);
    await page.locator(".valuation-method-grid").screenshot({ path: `/tmp/valuation-methods-aligned-${width}.png` });
    await page.locator(".valuation-snapshot-card").screenshot({ path: `/tmp/valuation-snapshot-${width}.png` });
  });
}

for (const width of [1440, 390]) {
  test(`loads fund flow in 20-day batches and keeps earlier batches on failure at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await mockAnalysisApi(page);
    const offsets: number[] = [];
    let failOnce = true;
    await page.route("**/api/stock/600519/fund-flow-pages*", async (route) => {
      const cursor = new URL(route.request().url()).searchParams.get("cursor");
      const offset = cursor ? Number(cursor.split(":")[1]) : 0;
      offsets.push(offset);
      if (offset === 20 && failOnce) {
        failOnce = false;
        await route.fulfill({ status: 503, json: { message: "批次超时，请重试", code: "upstream_unavailable" } });
        return;
      }
      await route.fulfill({ json: {
        items: Array.from({ length: 20 }, (_, i) => ({
          date: new Date(Date.UTC(2026, 8, 24 - offset - i)).toISOString().slice(0, 10),
          main_net: i * 100, super_net: i * 80, large_net: i * 20, mid_net: -i * 10, small_net: -i * 90,
          source: "tdxhub_stock_fund_flow_estimate", source_api: "tdxhub.capital_flow", is_stale: false,
        })),
        total: 60, next_cursor: offset < 40 ? `session:${offset + 20}` : null,
        source: "tdxhub_stock_fund_flow_estimate", source_api: "tdxhub.capital_flow",
      } });
    });
    await page.goto("/stock/600519?tab=fund-flow#stock-details");
    await expect(page.getByText("已加载 20 / 60 个交易日 · 每批最多 20 日")).toBeVisible();
    expect(offsets).toEqual([0]);
    await expect(page.getByText("备选数据源：TDXHub 分笔估算")).toBeVisible();
    await page.getByRole("button", { name: "加载更多", exact: true }).click();
    await expect(page.getByText("后续批次加载失败，已加载数据仍可查看")).toBeVisible();
    await expect(page.getByText("已加载 20 / 60 个交易日 · 每批最多 20 日")).toBeVisible();
    await page.getByRole("button", { name: "重试加载更多", exact: true }).click();
    await expect(page.getByText("已加载 40 / 60 个交易日 · 每批最多 20 日")).toBeVisible();
    await page.getByRole("button", { name: "加载更多", exact: true }).click();
    await expect(page.getByText("已加载 60 / 60 个交易日 · 每批最多 20 日")).toBeVisible();
    await expect(page.getByRole("button", { name: "加载更多", exact: true })).toHaveCount(0);
    expect(offsets).toEqual([0, 20, 20, 40]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    await page.locator(".stock-fund-flow-card").screenshot({ path: `/tmp/fund-flow-batches-${width}.png` });
  });
}
