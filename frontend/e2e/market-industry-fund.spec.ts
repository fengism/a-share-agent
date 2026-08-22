import { expect, test, type Page } from "@playwright/test";

const user = { id: 7, username: "researcher", is_admin: false, must_change_password: false };

async function mockIndustryRankings(page: Page, requestedDates: string[]) {
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\//, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(user) });
  });
  await page.route("**/api/market/industry-rankings?**", async (route) => {
    const date = new URL(route.request().url()).searchParams.get("date") || "";
    requestedDates.push(date);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        source: "开盘红",
        date,
        fetched_at: "2026-08-21T08:00:00+00:00",
        fund_data_available: true,
        total: 1,
        sectors: [{
          rank: 1,
          name: "贵金属",
          change_pct: 5.338,
          code: "881169",
          up_count: null,
          down_count: null,
          leader: "",
          leader_change: null,
          amount: 47_051_213_914,
          net_inflow: 3_885_676_376,
          buy_amount: 19_932_149_027,
          sell_amount: -16_046_472_651,
          turnover_rate: 1.526,
          market_cap: 1_354_185_084_652,
          avg_change: 3.79,
        }],
      }),
    });
  });
}

for (const target of [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "mobile", width: 390, height: 844 },
]) {
  test(`shows Kaipanhong industry fund flows on ${target.name}`, async ({ page }) => {
    const requestedDates: string[] = [];
    await page.setViewportSize({ width: target.width, height: target.height });
    await mockIndustryRankings(page, requestedDates);

    await page.goto("/market?tab=industry-rank&industryDate=2026-08-20");

    await expect(page.getByText("行业资金与涨跌排行", { exact: true })).toBeVisible();
    await expect(page.getByText("开盘红", { exact: true })).toBeVisible();
    await expect(page.getByText("数据日期：2026-08-20", { exact: true })).toBeVisible();
    await expect(page.getByText("贵金属", { exact: true })).toBeVisible();
    await expect(page.getByText("38.9亿", { exact: true })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "涨跌幅", exact: true })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "净流入", exact: true })).toBeVisible();
    await expect(page.getByLabel("行业排行视图")).toHaveCount(0);
    await expect.poll(() => requestedDates).toContain("2026-08-20");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  });
}
