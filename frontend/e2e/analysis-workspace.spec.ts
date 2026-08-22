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

async function mockAnalysisApi(page: Page) {
  const watchlistWrites: unknown[] = [];
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\//, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(user) });
  });
  await page.route("**/api/stock/analysis-page/600519", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
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
            { time: "10:00", price: 1520, avg_price: 1516, volume: 180, amount: 273_600, change_pct: 0.66 },
          ],
        },
        valuation: { code: "600519", pe_ttm: 23.1, pb: 7.8, ps_ttm: 9.2, peers: [] },
        cached_analysis: analysisResult,
        partial: false,
        unavailable_sections: [],
      }),
    });
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
        peer_summary: { pe_median: 20, pb_median: 5, ps_median: 7, peer_count: 0, peers: [] },
        fair_values: {}, blended_fair_value: 1560, fair_value_range: [1450, 1650], valuation_view: "合理偏高", valuation_summary: "估值处于历史中位偏上",
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
    ".analysis-charts-section > .analysis-chart-card, .analysis-workspace__details > .ant-card",
  );
  expect(await alignedSurfaces.count()).toBeGreaterThanOrEqual(4);
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
    ".analysis-context-summary",
    ".analysis-charts-section > .ant-card",
    ".analysis-workspace__details > .ant-card",
  ].join(","));
  const surfaces = (await Promise.all(
    Array.from({ length: await surfaceLocator.count() }, (_, index) => surfaceLocator.nth(index).boundingBox()),
  )).filter((box): box is GeometryBox => box !== null);

  for (let leftIndex = 0; leftIndex < surfaces.length; leftIndex += 1) {
    for (let rightIndex = leftIndex + 1; rightIndex < surfaces.length; rightIndex += 1) {
      expect(boxesIntersect(surfaces[leftIndex], surfaces[rightIndex])).toBe(false);
    }
  }

  const toolbar = page.locator(".analysis-kline-card > .ant-card-body > .analysis-chart-toolbar");
  await expect(toolbar).toBeVisible();
  const [titleBox, toolbarBox] = await Promise.all([
    page.locator(".analysis-kline-card > .ant-card-head").boundingBox(),
    toolbar.boundingBox(),
  ]);
  expect(titleBox).not.toBeNull();
  expect(toolbarBox).not.toBeNull();
  expect(toolbarBox!.y).toBeGreaterThanOrEqual(titleBox!.y + titleBox!.height - 1);
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
  await expect(page.getByRole("region", { name: "分析上下文" })).toBeVisible();
  await expect(page.getByRole("region", { name: "决策重点与 AI 追问" })).toContainText("等待关键支撑确认后再评估");

  const historyBox = await page.getByRole("complementary", { name: "最近分析记录" }).boundingBox();
  const decisionBox = await page.getByRole("region", { name: "决策重点与 AI 追问" }).boundingBox();
  const contextBox = await page.getByRole("region", { name: "分析上下文" }).boundingBox();
  expect(historyBox).not.toBeNull();
  expect(historyBox!.width).toBeLessThanOrEqual(180);
  const analysisPageBox = await page.locator(".analysis-page").boundingBox();
  expect(analysisPageBox).not.toBeNull();
  expect(historyBox!.x).toBeLessThanOrEqual(analysisPageBox!.x);
  expect(decisionBox).not.toBeNull();
  expect(contextBox).not.toBeNull();
  expect(historyBox!.x + historyBox!.width).toBeLessThan(decisionBox!.x);
  expect(Math.abs(decisionBox!.x - contextBox!.x)).toBeLessThanOrEqual(2);
  expect(contextBox!.y).toBeGreaterThan(decisionBox!.y + decisionBox!.height);
  const sentimentText = page.locator(".analysis-context-summary__sentiment-copy strong");
  await expect(sentimentText).toHaveText("温和偏多，机构关注稳定但短线分歧仍在");
  const sentimentTextBox = await sentimentText.boundingBox();
  const sentimentPanelBox = await page.locator(".analysis-context-summary__sentiment").boundingBox();
  expect(sentimentTextBox).not.toBeNull();
  expect(sentimentPanelBox).not.toBeNull();
  expect(sentimentTextBox!.x).toBeGreaterThanOrEqual(sentimentPanelBox!.x - 1);
  expect(sentimentTextBox!.x + sentimentTextBox!.width).toBeLessThanOrEqual(
    sentimentPanelBox!.x + sentimentPanelBox!.width + 1,
  );
  expect(sentimentTextBox!.y + sentimentTextBox!.height).toBeLessThanOrEqual(
    sentimentPanelBox!.y + sentimentPanelBox!.height + 1,
  );
  await expect(page.locator(".analysis-sentiment-gauge")).toHaveCount(0);

  const valuationBox = await page.locator(".analysis-conclusion__metrics").boundingBox();
  const factorSectionBox = await page.locator(".analysis-conclusion__decision-grid").boundingBox();
  expect(valuationBox).not.toBeNull();
  expect(factorSectionBox).not.toBeNull();
  expect(factorSectionBox!.y - valuationBox!.y - valuationBox!.height).toBeGreaterThanOrEqual(16);

  const stockCode = page.locator(".analysis-header-card").getByText("600519", { exact: true });
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
    (element) => element.parentElement?.classList.contains("analysis-workspace__main"),
  )).toBe(true);

  await page.getByRole("button", { name: "加入自选" }).click();
  await expect.poll(() => watchlistWrites).toEqual([{ stock_code: "600519", note: "来自分析工作台" }]);
  await expect(page.getByText("已加入自选")).toBeVisible();

  await page.getByRole("button", { name: /失效条件/ }).click();
  await expect(page).toHaveURL(/\/chat\?prompt=/);
  expect(decodeURIComponent(page.url())).toContain("贵州茅台当前结论的失效条件是什么");
});

test("keeps all dimension scores in the left column and content in the right", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mockAnalysisApi(page);
  await page.goto("/analysis/600519");

  for (const label of ["基本面", "技术面", "估值面", "情绪面"]) {
    await page.getByRole("tab", { name: label }).click();
    const summary = page.getByRole("region", { name: `${label}概览` });
    const score = page.getByRole("region", { name: `${label}评分` });
    const content = page.getByRole("region", { name: `${label}详情` });
    await expect(summary).toBeVisible();
    await expect(score).toBeVisible();
    await expect(content).toBeVisible();

    const [summaryBox, scoreBox, contentBox] = await Promise.all([
      summary.boundingBox(),
      score.boundingBox(),
      content.boundingBox(),
    ]);
    expect(summaryBox).not.toBeNull();
    expect(scoreBox).not.toBeNull();
    expect(contentBox).not.toBeNull();
    expect(boxesIntersect(scoreBox!, contentBox!)).toBe(false);
    expect(scoreBox!.x + scoreBox!.width).toBeLessThanOrEqual(contentBox!.x);
    expect(Math.abs(scoreBox!.y - contentBox!.y)).toBeLessThanOrEqual(2);
    expect(scoreBox!.x).toBeGreaterThanOrEqual(summaryBox!.x - 1);
    expect(contentBox!.x + contentBox!.width).toBeLessThanOrEqual(summaryBox!.x + summaryBox!.width + 1);
  }

  const signalListBox = await page.locator(".analysis-dimension-summary__tags").first().boundingBox();
  expect(signalListBox).not.toBeNull();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
});

test("loads a historical snapshot without the informational banner", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mockAnalysisApi(page);
  await page.goto("/analysis/600519?date=20260820");

  await expect(page.getByText("AI 综合研判")).toBeVisible();
  await expect(page.getByText("正在查看 2026-08-20 的历史分析快照")).toHaveCount(0);
  await expect(page.getByText("AI 结论与评分保持为当日结果")).toHaveCount(0);
});

test("keeps the mobile workspace decision-first without horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockAnalysisApi(page);
  await page.goto("/analysis/600519");

  await expect(page.getByRole("button", { name: "打开导航菜单" })).toBeVisible();
  await expect(page.getByRole("navigation", { name: "全局快捷操作" })).toHaveCount(0);
  await expect(page.getByRole("region", { name: "决策重点与 AI 追问" })).toBeVisible();

  const decisionBox = await page.getByRole("region", { name: "决策重点与 AI 追问" }).boundingBox();
  const contextBox = await page.getByRole("region", { name: "分析上下文" }).boundingBox();
  const historyBox = await page.getByRole("complementary", { name: "最近分析记录" }).boundingBox();
  expect(decisionBox).not.toBeNull();
  expect(contextBox).not.toBeNull();
  expect(historyBox).not.toBeNull();
  expect(contextBox!.y).toBeGreaterThan(decisionBox!.y);
  expect(historyBox!.y).toBeGreaterThan(contextBox!.y);
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
