import { expect, test } from "./base";

const mockConceptApi = async (page: import("@playwright/test").Page) => {
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\//, async (route) => {
    const path = decodeURIComponent(new URL(route.request().url()).pathname);
    let body: unknown = [];
    if (path === "/api/auth/me") body = { id: 7, username: "researcher", is_admin: false, must_change_password: false };
    else if (path === "/api/config") body = {};
    else if (path === "/api/market/concepts") body = [{
      name: "固态电池",
      stock_count: 30,
      change_pct: 2.1,
      change_date: "2026-11-06",
      up_count: 20,
      down_count: 8,
      limit_up_count: 3,
      sample_count: 30,
    }];
    else if (path === "/api/market/hot-rank/ths/concept") body = [{
      rank: 1,
      code: "885001",
      name: "固态电池",
      change_pct: 2.1,
      hot_value: 98.2,
      hot_tag: "主线",
      tag: "新能源",
    }];
    else if (path === "/api/market/mainline") body = {
      source: "财联社",
      fetched_at: "2026-11-06T15:00:00",
      style: null,
      items: [{
        title: "固态电池",
        description: "产业化提速",
        continued_days: 2,
        hot: 1,
        plates: [{
          code: "885001",
          name: "固态电池",
          reason: "产业化提速",
          rise_count: 20,
          change_pct: 2.1,
          article_title: "",
          faucets: [{ code: "300750", name: "宁德时代", change_pct: 1.2, reason: "龙头" }],
        }],
      }],
    };
    else if (path.endsWith("/constituents")) body = {
      concept: "固态电池",
      total: 2,
      quote_covered: 2,
      quote_source: "eastmoney",
      quoted_at: "2026-11-06T15:00:00",
      items: [
        { code: "300750", name: "宁德时代", price: 250.5, change_pct: 1.2, amount: 123456789, quote_source: "eastmoney", related_concepts: ["锂电池"] },
        { code: "002460", name: "赣锋锂业", price: 45.6, change_pct: -0.8, amount: 98765432, quote_source: "eastmoney", related_concepts: ["锂矿"] },
      ],
      related_concepts: [{ name: "锂电池", change_pct: 1.5, stock_count: 80 }],
    };
    else if (path.endsWith("/index")) body = {
      concept: "固态电池",
      days: 30,
      base: 1000,
      constituent_total: 2,
      constituent_used: 2,
      truncated: false,
      items: [
        { date: "2026-11-05", open: 1000, high: 1010, low: 995, close: 1005, change_pct: 0.5, amount: 1, up_count: 1, down_count: 1, limit_up_count: 0, limit_down_count: 0, sample_count: 2 },
        { date: "2026-11-06", open: 1005, high: 1025, low: 1000, close: 1021, change_pct: 1.6, amount: 1, up_count: 2, down_count: 0, limit_up_count: 0, limit_down_count: 0, sample_count: 2 },
      ],
    };
    await route.fulfill({ json: body });
  });
};

for (const width of [1440, 390]) {
  test(`concept workspace renders at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await mockConceptApi(page);
    await page.goto("/concept?concept=固态电池");
    await expect(page.getByRole("heading", { name: /概念/ })).toBeVisible();
    await expect(page.getByText("把一个概念当作一个组合")).toBeVisible();
    await expect(page.getByPlaceholder("搜索概念，例如「固态电池」")).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });
}
