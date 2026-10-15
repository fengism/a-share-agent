import { expect, test } from "@playwright/test";

test("separates futures quotes and static trade references", async ({ page }) => {
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\//, async route => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown = [];
    if (path === "/api/auth/me") body = { id: 7, username: "researcher", is_admin: false, must_change_password: false };
    else if (path === "/api/config") body = {};
    else if (path.endsWith("/macro/all")) body = { trade: {} };
    else if (path.endsWith("/commodities")) body = { query: "all", total_count: 1, items: [{
      symbol: "碳酸锂", name: "碳酸锂连续", contract: "LC0", category: "新能源金属", unit: "元/吨",
      latest_price: 100, date: "2026-09-24", description: "静态说明", related_chains: ["锂电池"],
    }] };
    else if (path.endsWith("/customs-trade")) body = { query: "all", latest_month_summary: null, recent_12m_macro_trend: [], matched_commodity_profiles: [{
      commodity: "光伏", category: "新能源", trade_type: "出口", unit: "参考单位", description: "静态说明", key_target_markets: "参考市场", related_a_stocks: ["示例公司"], industry_chains: ["光伏"],
    }] };
    await route.fulfill({ json: body });
  });
  await page.goto("/macro?tab=commodities");
  await expect(page.getByText("大宗商品期货连续 / 主力合约行情")).toBeVisible();
  await expect(page.getByText(/不是现货采购价/)).toBeVisible();
  await expect(page.getByText("2026-09-24 · 最近报价")).toBeVisible();
  await page.goto("/macro?tab=trade");
  await expect(page.getByText("重点商品与关联公司参考（静态资料）")).toBeVisible();
  await expect(page.getByText(/不是当期海关统计/)).toBeVisible();
  await expect(page.getByRole("columnheader", { name: "关联公司（静态，非受益判断）" })).toBeVisible();
});
