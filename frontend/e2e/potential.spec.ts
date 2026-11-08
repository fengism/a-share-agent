import { expect, test, type Page } from "./base";

const user = { id: 11, username: "potential-tester", is_admin: false, must_change_password: false };

const stock = (overrides: Record<string, unknown>) => ({
  code: "600519",
  name: "贵州茅台",
  price: 1688.0,
  change_pct: 2.35,
  market_cap: 2.1e12,
  turnover_pct: 12.5,
  amount: 5.4e9,
  industry: "白酒",
  strategies: ["均线多头"],
  signal_types: ["trend"],
  signal_date: "2026-11-06",
  signal_age_days: 1,
  score: 4.8,
  signal_score: 1.2,
  quality_score: 0.8,
  fundamental_score: 0.7,
  theme_score: 0.6,
  themes: ["消费复苏"],
  sector_strength: 0.4,
  risk_flags: [],
  reason: "趋势与基本面共振",
  category: "anchor",
  category_label: "机构中军",
  ...overrides,
});

const daily = {
  date: "2026-11-06",
  generated_at: "2026-11-06 16:00:00",
  universe_size: 5200,
  evaluated: 4800,
  failed_count: 12,
  market_regime: "bull",
  market_note: null,
  market_emotion: "strong",
  advance_ratio: 0.62,
  limit_up_count: 88,
  limit_down_count: 3,
  median_change_pct: 0.42,
  hot_themes: ["消费复苏", "机器人"],
  top_picks: [
    stock({}),
    stock({
      code: "300750",
      name: "宁德时代",
      price: 262.4,
      change_pct: -0.86,
      industry: "电池",
      category: "quality",
      category_label: "价值优选",
      score: 4.5,
      fundamental_score: 0.82,
    }),
  ],
  items: [
    stock({}),
    stock({
      code: "300750",
      name: "宁德时代",
      price: 262.4,
      change_pct: -0.86,
      industry: "电池",
      category: "quality",
      category_label: "价值优选",
      score: 4.5,
      fundamental_score: 0.82,
    }),
    stock({
      code: "002594",
      name: "比亚迪",
      price: 318.5,
      change_pct: 1.12,
      industry: "汽车整车",
      category: "pioneer",
      category_label: "趋势先锋",
      score: 4.2,
    }),
  ],
};

const performance = {
  date: "2026-11-06",
  days: 5,
  generated_at: "2026-11-06 16:05:00",
  item_count: 3,
  evaluated_count: 3,
  win_rate: 0.67,
  average_return_pct: 3.42,
  median_return_pct: 2.8,
  average_excess_pct: 1.9,
  benchmark_return_pct: 0.6,
  profit_loss_ratio: 1.85,
  positive_count: 2,
  negative_count: 1,
  message: null,
  items: [
    {
      code: "600519",
      name: "贵州茅台",
      industry: "白酒",
      entry_price: 1688.0,
      exit_price: 1742.0,
      return_pct: 3.2,
      benchmark_return_pct: 0.6,
      excess_return_pct: 2.6,
      max_return_pct: 4.1,
      max_drawdown_pct: -1.2,
    },
  ],
};

const runStatus = {
  running: false,
  status: "idle",
  date: "2026-11-06",
  started_at: null,
  finished_at: null,
  error: null,
};

async function mockPotential(page: Page) {
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\//, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === "/api/auth/me") return route.fulfill({ json: user });
    if (pathname === "/api/potential/dates") {
      return route.fulfill({ json: [{ date: "2026-11-06", count: 3 }] });
    }
    if (pathname === "/api/potential/latest") return route.fulfill({ json: daily });
    if (pathname === "/api/potential/performance") return route.fulfill({ json: performance });
    if (pathname === "/api/potential/run/status") return route.fulfill({ json: runStatus });
    if (pathname === "/api/watchlist") {
      return route.fulfill({ json: { source: "tencent", quoted_at: "", items: [] } });
    }
    return route.fulfill({ json: [] });
  });
}

const noHorizontalOverflow = async (page: Page) => {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
};

for (const width of [1440, 390]) {
  test(`potential renders radar picks at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mockPotential(page);
    await page.goto("/potential");

    await expect(page.getByText("每日潜力股", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("今日精选金股")).toBeVisible();
    await expect(page.getByText("机构中军").first()).toBeVisible();
    await expect(page.getByText("价值优选").first()).toBeVisible();
    await expect(page.getByText("历史表现复盘")).toBeVisible();
    await expect(page.getByText("盈亏比").first()).toBeVisible();
    await expect(page.getByText("贵州茅台").first()).toBeVisible();
    await noHorizontalOverflow(page);
  });
}

test("potential category tags use theme-aware non-price colors", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await mockPotential(page);
  await page.goto("/potential");

  const anchor = page.locator(".potential-category--anchor").first();
  const quality = page.locator(".potential-category--quality").first();
  await expect(anchor).toBeVisible();
  await expect(quality).toBeVisible();

  const colors = await page.evaluate(() => {
    const read = (sel: string) => {
      const el = document.querySelector(sel) as HTMLElement | null;
      return el ? getComputedStyle(el).color : "";
    };
    return {
      anchor: read(".potential-category--anchor"),
      quality: read(".potential-category--quality"),
      pioneer: read(".potential-category--pioneer"),
    };
  });

  expect(colors.anchor).not.toBe(colors.quality);
  // 红/绿仅用于涨跌：类别色不得落到 A 股涨跌红绿上
  for (const color of Object.values(colors)) {
    expect(color).not.toBe("rgb(240, 68, 56)");
    expect(color).not.toBe("rgb(18, 183, 106)");
  }
});
