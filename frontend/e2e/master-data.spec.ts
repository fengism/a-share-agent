import { expect, test } from "./base";

const mockMasterDataApi = async (page: import("@playwright/test").Page) => {
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\//, async (route) => {
    const path = decodeURIComponent(new URL(route.request().url()).pathname);
    let body: unknown = [];
    if (path === "/api/auth/me") body = { id: 7, username: "researcher", is_admin: false, must_change_password: false };
    else if (path === "/api/config") body = {};
    else if (path === "/api/stock-profile/summary") body = {
      total: 2,
      has_business_count: 2,
      has_listing_date_count: 1,
      last_updated_at: "2026-11-06T15:00:00",
      market_group_counts: { A: 1, HK: 1 },
      board_counts: { 主板: 1, 创业板: 1 },
    };
    else if (path === "/api/stock-profile/records") body = {
      items: [
        {
          id: 1,
          stock_code: "600519.SH",
          stock_name: "贵州茅台",
          market_group: "A",
          exchange: "SSE",
          board: "主板",
          listing_date: "2001-08-27",
          main_business: "茅台酒及系列酒的生产与销售",
          products: "茅台酒",
          business_scope: "白酒生产、销售",
          province: "贵州",
          city: "遵义",
          legal_repr: "丁雄军",
          registered_capital: "125619.78万元",
          website: "www.moutaichina.com",
          company_intro: "贵州茅台酒股份有限公司主营茅台酒及系列酒。",
          sw_level1_name: "食品饮料",
          sw_level2_name: "白酒",
          source: "manual",
          updated_at: "2026-11-06T15:00:00",
          is_manual_override: false,
          revision: "1",
          source_version: "1",
          setup_date: "1999-11-20",
          industry: "食品饮料",
          sw_level3_name: "白酒",
          created_at: "2026-01-01T00:00:00",
        },
        {
          id: 2,
          stock_code: "00700.HK",
          stock_name: "腾讯控股",
          market_group: "HK",
          exchange: "HKEX",
          board: "主板",
          listing_date: null,
          main_business: "互联网增值服务",
          products: "游戏、广告",
          business_scope: "互联网服务",
          province: "广东",
          city: "深圳",
          legal_repr: "马化腾",
          registered_capital: "",
          website: "www.tencent.com",
          company_intro: "",
          sw_level1_name: "传媒",
          sw_level2_name: "游戏",
          source: "sync",
          updated_at: "2026-11-06T15:00:00",
          is_manual_override: false,
          revision: "1",
          source_version: "1",
          setup_date: null,
          industry: "传媒",
          sw_level3_name: "游戏",
          created_at: "2026-01-01T00:00:00",
        },
      ],
      page: 1,
      page_size: 20,
      total: 2,
    };
    await route.fulfill({ json: body });
  });
};

for (const width of [1440, 390]) {
  test(`master data profile renders at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await mockMasterDataApi(page);
    await page.goto("/master-data?tab=profile");
    await expect(page.getByRole("heading", { name: /基础数据管理/ })).toBeVisible();
    await expect(page.getByText("全市场股票数")).toBeVisible();
    await expect(page.getByRole("link", { name: "贵州茅台", exact: true })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });
}
