import { expect, test, type Page } from "@playwright/test";
import { stat } from "node:fs/promises";

const user = {
  id: 7,
  username: "researcher",
  is_admin: false,
  must_change_password: false,
};

const researchFramework = {
  information_quality: {
    grade: "B",
    grade_rationale: "财务资料充分，管理层资料仍有限",
    evidence_confidence: 0.78,
    investment_certainty: 0.61,
    coverage_summary: "覆盖财务、估值、行业和主要风险",
    limitations: ["部分分部数据没有报告期"],
  },
  business_model: {
    economic_engine: "通过品牌溢价和稳定复购获得现金流",
    revenue_drivers: ["核心产品销量"],
    segment_quality: [],
    earnings_quality: "经营现金流与利润方向一致",
    operating_leverage: "成本相对稳定",
    strengths: ["品牌认知稳定"],
    concerns: ["渠道库存需跟踪"],
  },
  moat: {
    moats: [{
      moat_type: "brand_pricing",
      evidence: ["核心产品价格稳定"],
      counterevidence: ["竞品持续扩张"],
      strength: "strong",
      direction: "stable",
      durability: "仍具持续性",
      threats: ["消费偏好迁移"],
      confidence: 0.75,
    }],
    overall_durability: "中长期仍需渠道数据验证",
    key_threats: ["需求结构变化"],
  },
  management: {
    track_record: "经营策略保持连贯",
    capital_allocation: "主业投入与分红并重",
    shareholder_alignment: "治理结构稳定",
    succession_or_key_person_risk: "接班安排需跟踪",
    strengths: [],
    concerns: [],
    confidence: 0.65,
  },
  industry_position: {
    secular_context: "行业进入存量竞争",
    value_chain_position: "品牌与渠道环节",
    growth_drivers: ["产品结构升级"],
    competitive_position: "头部位置",
    technology_or_obsolescence_risk: "较低",
    concentration_risks: ["单一品类占比较高"],
    confidence: 0.68,
  },
  inversion: {
    bear_case: "需求走弱与渠道去库存同时发生",
    risks: [],
    bias_checks: ["避免用历史高增长外推未来"],
  },
  valuation: {
    method_summary: "复用现有估值结果",
    current_valuation: "估值处于合理区间",
    assumptions: ["利润保持稳定"],
    scenarios: {
      bull: { scenario: "bull", assumptions: ["需求恢复"], valuation_view: "偏低", fair_value_range: [1600, 1800], key_drivers: [], invalidating_conditions: ["需求未恢复"] },
      base: { scenario: "base", assumptions: ["稳健增长"], valuation_view: "合理", fair_value_range: [1450, 1650], key_drivers: [], invalidating_conditions: ["利润下滑"] },
      bear: { scenario: "bear", assumptions: ["需求承压"], valuation_view: "偏高", fair_value_range: null, key_drivers: [], invalidating_conditions: ["库存快速下降"] },
    },
    margin_of_safety: "等待价格回落或盈利上修",
    limitations: ["未独立计算反向 DCF"],
  },
  actions: {
    new_investor_action: "watch",
    holder_action: "hold",
    rationale: "当前赔率尚不突出",
    buy_or_add_range: [1400, 1480],
    add_triggers: ["估值进入安全边际"],
    sell_triggers: ["现金流持续弱于利润"],
    thesis_breakers: ["品牌定价权持续削弱"],
    monitoring_metrics: ["批价", "经营现金流"],
  },
  data_gaps: [{
    topic: "渠道库存",
    missing_data: "缺少统一口径",
    decision_impact: "影响需求判断",
    follow_up: "核对公告与渠道调研",
  }],
};

const analysisResult = {
  stock_code: "600519",
  stock_name: "贵州茅台",
  analysis_date: "2026-08-26",
  current_price: 1520,
  fundamental: { score: 8.2, summary: "盈利质量稳定", strengths: [], risks: [] },
  technical: { score: 7.1, summary: "趋势稳定", strengths: [], risks: [] },
  sentiment: { score: 6.8, summary: "情绪温和", strengths: [], risks: [] },
  valuation_view: "合理",
  fair_value_range: [1450, 1650],
  blended_fair_value: 1560,
  overall_rating: 7.6,
  overall_summary: "基本面稳健",
  estimated_price_range: [1480, 1680],
  signal: "buy",
  confidence: 0.78,
  key_factors: ["盈利韧性"],
  risk_warnings: ["需求走弱"],
  research_framework: researchFramework,
};

async function mockResearchApi(page: Page, cachedAnalysis: unknown = analysisResult) {
  const cancelledJobs: string[] = [];
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\//, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route(
    /\/api\/stock\/600519\/(?:indicators|valuation-detail|news-categorized|sentiment|retail-sentiment)$/,
    async (route) => {
      await route.fulfill({ status: 200, contentType: "application/json", body: "null" });
    },
  );
  await page.route(/\/api\/stock\/600519\/financial\?.*$/, async (route) => {
    const statementType = new URL(route.request().url()).searchParams.get("type");
    const records = {
      balance: [{
        REPORT_DATE: "2026-06-30",
        TOTAL_ASSETS: 300_000_000,
        TOTAL_LIABILITIES: 80_000_000,
        MONETARYFUNDS: 90_000_000,
        INVENTORY: 30_000_000,
        TOTAL_CURRENT_ASSETS: 180_000_000,
        TOTAL_CURRENT_LIAB: 60_000_000,
      }],
      profit: [{
        REPORT_DATE: "2026-06-30",
        OPERATE_INCOME: 120_000_000,
        OPERATE_INCOME_YOY: 12.5,
        OPERATE_COST: 30_000_000,
        PARENT_NETPROFIT: 60_000_000,
        PARENT_NETPROFIT_YOY: 10.5,
        DEDUCT_PARENT_NETPROFIT: 58_000_000,
        DEDUCT_PARENT_NETPROFIT_YOY: 9.8,
        BASIC_EPS: 4.75,
      }],
      cashflow: [{
        REPORT_DATE: "2026-06-30",
        NETCASH_OPERATE: 65_000_000,
        NETCASH_OPERATE_YOY: 8.6,
        NETCASH_INVEST: -15_000_000,
      }],
    }[statementType ?? ""] ?? [];
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(records) });
  });
  await page.route("**/api/stock/600519/revenue-breakdown", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        code: "600519",
        symbol: "sh600519",
        name: "贵州茅台",
        source: "sina",
        amount_unit: "CNY_yuan",
        amount_unit_inferred: true,
        by_product: [{
          id: "1",
          class_name: "茅台酒",
          is_sub_item: false,
          revenue: 100_000_000,
          cost: 10_000_000,
          gross_profit: 90_000_000,
          revenue_share_pct: 90,
          gross_margin_pct: 90,
        }],
        by_business: [],
        by_region: [],
      }),
    });
  });
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(user) });
  });
  // Exercise the browser-side enhanced PDF fallback. The backend vector PDF
  // endpoint is covered separately and is intentionally unavailable here.
  await page.route("**/api/analysis/export-pdf", async (route) => {
    await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "offline" }) });
  });
  await page.route("**/api/analysis/600519/export-pdf?**", async (route) => {
    await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ detail: "offline" }) });
  });
  await page.route(/\/api\/stock\/search(?:\?.*)?$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([{ code: "600519", name: "贵州茅台", price: 1520 }]),
    });
  });
  const pageData = {
        stock_info: { code: "600519", name: "贵州茅台", concepts: [] },
        kline: {
          code: "600519",
          period: "daily",
          adjust: "qfq",
          source: "mock",
          adjustment_verified: true,
          items: [
            { date: "2026-08-21", open: 1490, close: 1500, high: 1510, low: 1480, volume: 1000, amount: 1_500_000, amplitude: 2.0, turnover_pct: 0.2, change_pct: 0.7 },
            { date: "2026-08-24", open: 1500, close: 1510, high: 1520, low: 1495, volume: 1100, amount: 1_661_000, amplitude: 1.7, turnover_pct: 0.22, change_pct: 0.67 },
            { date: "2026-08-25", open: 1510, close: 1515, high: 1525, low: 1502, volume: 1050, amount: 1_590_750, amplitude: 1.5, turnover_pct: 0.21, change_pct: 0.33 },
            { date: "2026-08-26", open: 1515, close: 1520, high: 1530, low: 1510, volume: 1200, amount: 1_824_000, amplitude: 1.3, turnover_pct: 0.24, change_pct: 0.33 },
          ],
        },
        intraday: null,
        valuation: null,
        cached_analysis: cachedAnalysis,
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
  await page.route("**/api/analysis/history/all?**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { stock_code: "600519", stock_name: "贵州茅台", analysis_date: "2026-08-26", overall_rating: 7.6, signal: "buy", confidence: 0.78, can_delete: true },
        { stock_code: "600519", stock_name: "贵州茅台", analysis_date: "2026-08-20", overall_rating: 7.2, signal: "hold", confidence: 0.7, can_delete: true },
      ]),
    });
  });
  await page.route("**/api/analysis/600519/history/20260820", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ...analysisResult, analysis_date: "2026-08-20", research_framework: null }),
    });
  });
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\/watchlist$/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        source: "mock",
        quoted_at: "2026-08-26T15:00:00+08:00",
        items: [],
      }),
    });
  });
  await page.route("**/api/workflows/*", async (route) => {
    if (route.request().method() === "DELETE") {
      cancelledJobs.push(route.request().url());
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "cancelled" }),
      });
      return;
    }
    await route.fallback();
  });
  return { cancelledJobs };
}

test("sends the stock picker entry to the stock profile page, not AI analysis", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mockResearchApi(page);
  await page.goto("/analysis");
  await expect(page.getByRole("heading", { name: /个股/ })).toBeVisible();

  // 用前缀匹配而不是完整文案：placeholder 已随港股搜索支持改为
  // "如 600519、00700 或 贵州茅台、腾讯控股"，全量匹配会随文案调整而失效
  const stockSearchInput = page.getByPlaceholder(/输入股票代码或名称/);
  await stockSearchInput.fill("600519");
  await stockSearchInput.press("Enter");

  // 个股入口默认进入个股资料页
  await expect(page).toHaveURL(/\/stock\/600519$/);
});

test("renders investment research as the default dimension of the stock research page", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mockResearchApi(page);
  // 个股选股入口（/analysis）的搜索框现在默认进入个股资料页（/stock/:code），
  // 投资研判页改为直接访问，不再由选股入口跳转。
  await page.goto("/analysis/600519");

  await expect(page.getByRole("tab", { name: "研究结论" })).toHaveAttribute("aria-selected", "true");
  const researchConclusion = page.locator(".analysis-research-conclusion");
  await expect(researchConclusion.getByRole("heading", { name: "综合研判" })).toBeVisible();
  await expect(researchConclusion.getByLabel("决策重点与 AI 追问")).toBeVisible();
  await expect(researchConclusion.getByRole("heading", { name: "生意与盈利引擎" })).toBeVisible();
  await expect(researchConclusion.locator(".ant-segmented-item-selected")).toContainText("精简阅读");
  await expect(page.locator(".analysis-workspace__main").getByRole("heading", { name: "综合研判" })).toHaveCount(0);
  await expect(page.getByText("AI 正在研究")).toHaveCount(0);
  await expect(page.getByLabel("证据可信度78%")).toBeVisible();
  await expect(page.getByLabel("股票行情摘要")).toBeVisible();
  await expect(page.locator(".analysis-research-overview")).toBeVisible();
  const conclusionTypography = await researchConclusion.evaluate((conclusion) => {
    const title = conclusion.querySelector<HTMLElement>(".analysis-conclusion__section-header h2");
    const eyebrow = conclusion.querySelector<HTMLElement>(".analysis-conclusion__eyebrow");
    const summary = conclusion.querySelector<HTMLElement>(".analysis-conclusion__summary");
    const metric = conclusion.querySelector<HTMLElement>(".analysis-conclusion__metric strong");
    if (!title || !eyebrow || !summary || !metric) return null;
    return {
      family: getComputedStyle(conclusion).fontFamily,
      bodySize: getComputedStyle(conclusion).fontSize,
      bodyLineHeight: getComputedStyle(conclusion).lineHeight,
      titleSize: getComputedStyle(title).fontSize,
      eyebrowSize: getComputedStyle(eyebrow).fontSize,
      summarySize: getComputedStyle(summary).fontSize,
      metricSize: getComputedStyle(metric).fontSize,
    };
  });
  expect(conclusionTypography).toEqual({
    family: expect.stringContaining("PingFang SC"),
    bodySize: "15px",
    bodyLineHeight: "25.5px",
    titleSize: "18px",
    eyebrowSize: "12px",
    summarySize: "18px",
    metricSize: "20px",
  });
  await expect(page.locator(".analysis-panels-card, .analysis-charts-section")).toHaveCount(0);
  await expect(page.getByRole("tab", { name: "技术面", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "打开报告模式" })).toBeVisible();
  await expect(page.getByRole("complementary", { name: "最近分析记录" })).toBeVisible();
  await expect(page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).resolves.toBe(true);

  await page.getByRole("link", { name: "个股资料", exact: true }).click();
  await page.locator(".stock-deferred-section").scrollIntoViewIfNeeded();
  await expect(page.getByRole("tab", { name: "财务", exact: true })).toHaveAttribute("aria-selected", "true");
  const financialTypography = await page.locator(".stock-deferred-section .financial-data-sections").first().evaluate((section) => {
    const heading = section.querySelector<HTMLElement>(".financial-data-section__header-title");
    const tableHeading = section.querySelector<HTMLElement>(".ant-table-thead th");
    const tableCell = section.querySelector<HTMLElement>(".terminal-table-row td");
    if (!heading || !tableHeading || !tableCell) return null;
    return {
      headingSize: getComputedStyle(heading).fontSize,
      tableHeadingSize: getComputedStyle(tableHeading).fontSize,
      tableCellSize: getComputedStyle(tableCell).fontSize,
      tableCellLineHeight: getComputedStyle(tableCell).lineHeight,
    };
  });
  expect(financialTypography).toEqual({
    headingSize: "15px",
    tableHeadingSize: "12px",
    tableCellSize: "13px",
    tableCellLineHeight: "19.5px",
  });

  await page.getByRole("link", { name: "AI 分析", exact: true }).click();
  await page.getByRole("tab", { name: "研究结论" }).click();
  await page.getByRole("button", { name: /查看估值明细/ }).click();
  await expect(page).toHaveURL(/\/stock\/600519\?tab=valuation#stock-details$/);
});

test("keeps the stock research summary readable on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockResearchApi(page);
  await page.goto("/analysis/600519");

  await expect(page.getByLabel("股票行情摘要")).toBeVisible();
  await expect(page.getByRole("heading", { name: "综合研判" })).toBeVisible();
  await expect(page.getByLabel("决策重点与 AI 追问")).toBeVisible();
  await expect(page.locator(".analysis-header-card__metrics").evaluate((element) => (
    getComputedStyle(element).gridTemplateColumns.split(" ").length
  ))).resolves.toBe(2);
  await expect(page.locator(".analysis-research-overview").evaluate((element) => (
    getComputedStyle(element).gridTemplateColumns.split(" ").length
  ))).resolves.toBe(1);
  await expect(page.locator(".analysis-conclusion__summary").evaluate((element) => (
    getComputedStyle(element).fontSize
  ))).resolves.toBe("16px");
  await expect(page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).resolves.toBe(true);
});

test("exports the consolidated stock research report as a PDF", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mockResearchApi(page);
  await page.route("**/api/analysis/export-pdf", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/pdf",
      headers: { "Content-Disposition": 'attachment; filename="600519-analysis.pdf"' },
      body: "%PDF-1.4\n% mocked vector report\n".padEnd(1_200, "0"),
    });
  });
  await page.goto("/analysis/600519");
  await expect(page.getByRole("heading", { name: "综合研判" })).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "导出" }).click();
  await page.getByRole("menuitem", { name: /导出为 PDF/ }).click();
  const download = await downloadPromise;

  expect(download.suggestedFilename()).toMatch(/\.pdf$/);
  const downloadPath = await download.path();
  expect(downloadPath).toBeTruthy();
  expect((await stat(downloadPath!)).size).toBeGreaterThan(1_000);
  await download.saveAs("/tmp/stock-analysis-report.pdf");
  await expect(page.getByText("PDF 研报已生成并开始下载")).toBeVisible();
});

test("includes financial appendices in the focused research PDF", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mockResearchApi(page);
  await page.goto("/investment-research/600519");
  await expect(page.getByRole("heading", { name: /投资研究报告/ })).toBeVisible();
  const typography = await page.locator(".investment-research-report").evaluate((report) => {
    const framework = report.querySelector<HTMLElement>(".research-framework");
    const title = report.querySelector<HTMLElement>(".investment-research-report__header h2");
    const header = report.querySelector<HTMLElement>(".investment-research-report__header");
    const sectionTitle = report.querySelector<HTMLElement>(".research-section__header h4");
    const eyebrow = report.querySelector<HTMLElement>(".research-eyebrow");
    const chapterLink = report.querySelector<HTMLElement>(".research-reading-toolbar a");
    const supportingTitle = report.querySelector<HTMLElement>(".research-framework h5");
    if (!framework || !title || !header || !sectionTitle || !eyebrow || !chapterLink || !supportingTitle) return null;
    return {
      family: getComputedStyle(framework).fontFamily,
      bodySize: getComputedStyle(framework).fontSize,
      bodyLineHeight: getComputedStyle(framework).lineHeight,
      reportWidth: report.getBoundingClientRect().width,
      titleSize: getComputedStyle(title).fontSize,
      headerMarginBottom: getComputedStyle(header).marginBottom,
      headerPaddingBottom: getComputedStyle(header).paddingBottom,
      sectionTitleSize: getComputedStyle(sectionTitle).fontSize,
      eyebrowSize: getComputedStyle(eyebrow).fontSize,
      eyebrowSpacing: getComputedStyle(eyebrow).letterSpacing,
      chapterLinkSize: getComputedStyle(chapterLink).fontSize,
      supportingTitleSize: getComputedStyle(supportingTitle).fontSize,
    };
  });
  expect(typography).not.toBeNull();
  expect(typography?.family).toContain("PingFang SC");
  expect(typography?.bodySize).toBe("15px");
  expect(typography?.bodyLineHeight).toBe("25.5px");
  expect(typography?.reportWidth).toBeLessThanOrEqual(1120);
  expect(typography?.titleSize).toBe("28px");
  expect(typography?.headerMarginBottom).toBe("16px");
  expect(typography?.headerPaddingBottom).toBe("16px");
  expect(typography?.sectionTitleSize).toBe("18px");
  expect(typography?.eyebrowSize).toBe("12px");
  expect(typography?.eyebrowSpacing).toBe("0.5px");
  expect(typography?.chapterLinkSize).toBe("14px");
  expect(typography?.supportingTitleSize).toBe("14px");
  await page.screenshot({ path: "/tmp/stock-research-typography-desktop.png", fullPage: true });

  const downloadPromise = page.waitForEvent("download");
  const financialReadyPromise = page.waitForFunction(() => {
    const root = document.querySelector(".investment-research-report.pdf-exporting");
    const financial = root?.querySelector('[data-pdf-financial-ready="true"]');
    const revenue = root?.querySelector('[data-pdf-revenue-ready="true"]');
    const keyFinancialMetrics = root?.querySelector<HTMLElement>(".pdf-key-financial-metrics");
    const framework = root?.querySelector<HTMLElement>(".research-framework");
    const firstTableCell = root?.querySelector<HTMLElement>(".terminal-table-row td");
    const revenueRows = Array.from(
      root?.querySelectorAll(".revenue-breakdown-pdf .ant-table-tbody tr") ?? [],
    );
    const text = root?.textContent ?? "";
    return Boolean(
      financial
      && revenue
      && Number((revenue as HTMLElement).dataset.pdfRevenueRowCount) > 0
      && revenueRows.length > 0
      && revenueRows.every((row) => row.getBoundingClientRect().height > 0)
      && Number(keyFinancialMetrics?.dataset.pdfRowCount) === 19
      && keyFinancialMetrics.getBoundingClientRect().height > 0
      && keyFinancialMetrics.querySelectorAll(".ant-table-tbody tr").length === 19
      && text.includes("茅台酒")
      && text.includes("盈利与增长")
      && text.includes("毛利率")
      && text.includes("资产健康")
      && text.includes("流动比率")
      && text.includes("现金质量")
      && text.includes("现金利润比")
      && framework
      && firstTableCell
      && getComputedStyle(framework).fontSize === "16px"
      && getComputedStyle(firstTableCell).fontSize === "13px"
    );
  });
  await page.getByRole("button", { name: "导出 PDF" }).click();
  await financialReadyPromise;
  const download = await downloadPromise;

  expect(download.suggestedFilename()).toMatch(/^600519-投资研究-\d{8}\.pdf$/);
  await expect(page.getByText("PDF 导出成功")).toBeVisible();
  const downloadPath = await download.path();
  expect(downloadPath).toBeTruthy();
  expect((await stat(downloadPath!)).size).toBeGreaterThan(1_000);
  await download.saveAs("/tmp/stock-investment-research-report.pdf");
});

test("keeps historical legacy reports in the standalone namespace", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await mockResearchApi(page);
  await page.goto("/investment-research/600519?date=20260820");

  await expect(page.getByText("历史快照 · 2026-08-20")).toBeVisible();
  await expect(page.getByText("该研究快照由旧版框架生成，暂无结构化研究结论")).toBeVisible();
  await page.getByRole("link", { name: /贵州茅台/ }).first().click();
  await expect(page).toHaveURL(/\/investment-research\/600519\?date=20260826$/);
});

test("shows mobile history access without horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mockResearchApi(page);
  await page.goto("/investment-research/600519");

  await expect(page.getByRole("button", { name: "研究历史" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "生意与盈利引擎" })).toBeVisible();
  const mobileTypography = await page.locator(".investment-research-report").evaluate((report) => {
    const framework = report.querySelector<HTMLElement>(".research-framework");
    const title = report.querySelector<HTMLElement>(".investment-research-report__header h2");
    const header = report.querySelector<HTMLElement>(".investment-research-report__header");
    const toolbar = report.querySelector<HTMLElement>(".research-reading-toolbar");
    const section = report.querySelector<HTMLElement>(".research-section");
    if (!framework || !title || !header || !toolbar || !section) return null;
    return {
      bodySize: getComputedStyle(framework).fontSize,
      titleSize: getComputedStyle(title).fontSize,
      headerMarginBottom: getComputedStyle(header).marginBottom,
      headerPaddingBottom: getComputedStyle(header).paddingBottom,
      toolbarPaddingTop: getComputedStyle(toolbar).paddingTop,
      toolbarGap: getComputedStyle(toolbar).gap,
      sectionPaddingTop: getComputedStyle(section).paddingTop,
      sectionPaddingBottom: getComputedStyle(section).paddingBottom,
    };
  });
  expect(mobileTypography).toEqual({
    bodySize: "15px",
    titleSize: "24px",
    headerMarginBottom: "12px",
    headerPaddingBottom: "12px",
    toolbarPaddingTop: "4px",
    toolbarGap: "4px",
    sectionPaddingTop: "20px",
    sectionPaddingBottom: "20px",
  });
  await expect(page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).resolves.toBe(true);
  await page.screenshot({ path: "/tmp/stock-research-typography-mobile.png", fullPage: true });
  await page.getByRole("button", { name: "研究历史" }).click();
  await expect(page.getByRole("dialog", { name: "最近投资研究" })).toBeVisible();
});

test("redirects the legacy workbench root and keeps report deep links read only", async ({ page }) => {
  await mockResearchApi(page, null);
  await page.goto("/investment-research");
  await expect(page).toHaveURL(/\/analysis$/);
  await expect(page.getByRole("heading", { name: /个股/ })).toBeVisible();

  await page.goto("/investment-research/600519");
  await expect(page.getByRole("heading", { name: /投资研究报告/ })).toBeVisible();
  await expect(page.getByRole("button", { name: /开始研究|重新研究|取消研究/ })).toHaveCount(0);
  await page.getByRole("button", { name: /返回个股研究/ }).click();
  await expect(page).toHaveURL(/\/analysis\/600519\?panel=research$/);
});

for (const width of [1920, 1180, 390]) {
  test(`returns from bottom result to visible valuation details at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mockResearchApi(page);
    await page.route("**/api/analysis/600519/history/20260820", (route) => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ...analysisResult, analysis_date: "2026-08-20" }),
    }));
    await page.goto("/analysis/600519?date=20260820&panel=technical");
    const result = page.getByRole("region", { name: "个股分析结果", exact: true });
    await page.getByRole("link", { name: "查看结论", exact: true }).click();
    await expect(result.getByRole("tab", { name: "研究结论" })).toBeInViewport();
    // Carry the selected historical date into the profile valuation tab.
    await result.getByText("完整报告", { exact: true }).click();
    await result.getByRole("button", { name: "查看估值明细" }).click();
    await expect(page).toHaveURL(/\/stock\/600519\?tab=valuation&date=20260820#stock-details$/);
    await expect(page.getByRole("region", { name: "当前估值快照" })).toBeVisible();
    await expect(page.getByRole("tab", { name: "估值", exact: true })).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("heading", { name: "估值分析" })).toBeInViewport();
    await expect(page.getByText(/来自 2026-08-20 的历史报告/)).toBeVisible();
  });
}
