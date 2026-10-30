import { expect, test, type Page } from "@playwright/test";

const user = { id: 7, username: "review-tester", is_admin: false, must_change_password: false };

const review = {
  date: "2026-10-29",
  title: "A股市场每日复盘 - 2026-10-29",
  generated_at: "2026-10-29 16:10:00",
  market_summary: "指数震荡收涨，机器人主线领涨。",
  quality_status: "complete",
  generation_status: "llm",
  llm_review: "## 盘面综述\n\n指数缩量上行，机器人板块领涨。",
  sentiment_cycle: { stage: "主升共振", ladder_health: "无断层", evidence: ["空间板 6 板"] },
  previous_review_check: {
    review_date: "2026-10-28",
    verified_date: "2026-10-29",
    hit_count: 1,
    checked_count: 2,
    watchlist: [
      { name: "甲", code: "600001", change_pct: 10, hit: true, limit_up: true },
      { name: "乙", code: "600002", change_pct: -3.2, hit: false },
    ],
    indices: [{ name: "上证指数", previous_change_pct: 0.8, change_pct: -0.42 }],
  },
  cycle_trend: {
    points: [
      { date: "2026-10-28", stage: "修复回暖", stage_transition: "升级", limit_up_count: 36, break_rate: 0.18, index_change_pct: 0.85 },
      { date: "2026-10-29", stage: "主升共振", stage_transition: "升级", limit_up_count: 42, break_rate: 0.15, index_change_pct: 1.2 },
    ],
    stage_stats: [{ stage: "主升共振", occurrences: 2, next_day_up_ratio: 0.5 }],
  },
  scenario_plans: [{ name: "超预期", trigger: "放量高开", playbook: "加仓主线" }],
  next_day_watchlist: [{ name: "甲", role: "连板最高板", reason: "空间板", trigger: "竞价强度" }],
  key_levels: ["上证 3250 支撑"],
  event_impacts: [],
  index_review: { title: "指数", summary: "缩量上行", bullets: ["银行护盘"] },
  hotspot_review: { title: "热点", summary: "机器人领涨", bullets: ["减速器走强"] },
  dragon_tiger_review: { title: "龙虎榜", summary: "机构净买入", bullets: [] },
  risk_alerts: [],
  opportunities: ["机器人"],
  strategy_notes: ["持股待涨"],
  data_snapshot: {
    indices: [{ name: "上证指数", change_pct: 0.85 }],
    hot_stocks: [],
    hot_concepts: [],
    hot_industries: [],
    dragon_tiger: [],
    top_sectors: [{ name: "机器人", change_pct: 3.2 }],
    bottom_sectors: [{ name: "白酒", change_pct: -1.1 }],
    market_statistics: { limit_up_count: 42, break_rate: 0.18 },
    market_news: [],
    market_volume: { total_amount: 1.2e12 },
    macro_data: {},
  },
};

async function mockReviewPage(page: Page) {
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\//, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === "/api/auth/me") return route.fulfill({ json: user });
    if (pathname === "/api/daily-review/history") {
      return route.fulfill({
        json: {
          items: [{ date: review.date, title: review.title, generated_at: review.generated_at, market_summary: review.market_summary, can_delete: true }],
          total: 1,
          limit: 20,
          offset: 0,
        },
      });
    }
    if (pathname.startsWith("/api/daily-review/")) return route.fulfill({ json: review });
    return route.fulfill({ json: [] });
  });
}

for (const width of [1440, 1024, 390]) {
  test(`daily review keeps the conclusion and sections readable at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mockReviewPage(page);

    await page.goto("/daily-review?date=2026-10-29");

    // 首屏结论：核心指标与情绪阶段
    await expect(page.getByText("涨停家数")).toBeVisible();
    await expect(page.getByText("主升共振").first()).toBeVisible();

    // 章节目录可见
    await expect(page.getByRole("navigation", { name: "复盘章节导航" })).toBeVisible();

    // 折叠章节：展开「昨日复盘自检」后可见逐项对照
    const selfCheck = page.getByRole("button", { name: /昨日复盘自检/ }).last();
    await selfCheck.click();
    await expect(page.getByRole("table", { name: "观察锚点逐项对照" })).toBeVisible();

    // 无横向溢出
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  });
}
