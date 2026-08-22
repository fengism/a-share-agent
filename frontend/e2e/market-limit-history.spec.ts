import { expect, test, type Page } from "@playwright/test";

const user = { id: 7, username: "researcher", is_admin: false, must_change_password: false };

function historyItem(category: string) {
  return {
    code: category === "limit_down" ? "600376" : "603666",
    name: category === "limit_down" ? "首开股份" : "亿嘉和",
    limit_time: "14:55:34",
    open_time: "",
    seal_amount: 49_621_636,
    limit_tag: category === "limit_down" ? "" : "首板",
    limit_count: category === "limit_down" ? 0 : 1,
    themes: category === "limit_down" ? "房地产、地产链" : "机器人概念、医疗器械",
    net_inflow: category === "limit_down" ? -29_382_611 : 28_660_578,
    turnover: 526_093_870,
    turnover_rate: 12.12,
    market_cap: 4_286_293_311,
    reason: category === "limit_down" ? "" : "机器人概念",
    seal_money: 61_551_268,
    industry_id: category === "limit_down" ? "" : "801159",
    industry_limit_up_count: category === "limit_down" ? 0 : 1,
  };
}

async function mockMarketHistory(page: Page, requestedCategories: string[]) {
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\//, async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
  });
  await page.route("**/api/auth/me", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(user) });
  });
  await page.route("**/api/market/limit-history?**", async (route) => {
    const url = new URL(route.request().url());
    const category = url.searchParams.get("category") || "limit_up";
    requestedCategories.push(category);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        source: "开盘红",
        date: url.searchParams.get("date") || "2026-08-20",
        category,
        fetched_at: "2026-08-21T08:00:00+00:00",
        total: 1,
        items: [historyItem(category)],
      }),
    });
  });
}

for (const target of [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "mobile", width: 390, height: 844 },
]) {
  test(`shows Kaipanhong historical lists without overlap on ${target.name}`, async ({ page }) => {
    const requestedCategories: string[] = [];
    await page.setViewportSize({ width: target.width, height: target.height });
    await mockMarketHistory(page, requestedCategories);

    await page.goto("/market?tab=limit-up&mode=history&historyDate=2026-08-20");

    await expect(page.getByRole("heading", { name: "历史涨停", exact: true })).toBeVisible();
    await expect(page.getByText("亿嘉和", { exact: true })).toBeVisible();
    await expect(page.getByText("涨停原因", { exact: true }).first()).toBeVisible();
    await expect.poll(() => requestedCategories).toContain("limit_up");

    const controlCard = page.locator(".ant-card").filter({ hasText: "数据来源：开盘红" }).first();
    const detailCard = page.locator(".ant-card").filter({ hasText: "历史涨停明细" }).first();
    const [controlBox, detailBox] = await Promise.all([controlCard.boundingBox(), detailCard.boundingBox()]);
    expect(controlBox).not.toBeNull();
    expect(detailBox).not.toBeNull();
    expect((controlBox?.y || 0) + (controlBox?.height || 0)).toBeLessThanOrEqual((detailBox?.y || 0) + 1);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);

    await page.getByText("历史跌停", { exact: true }).click();
    await expect(page.getByRole("heading", { name: "历史跌停", exact: true })).toBeVisible();
    await expect(page.getByText("首开股份", { exact: true })).toBeVisible();
    await expect(page.getByText("跌停时间", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("涨停原因", { exact: true })).toHaveCount(0);
    await expect.poll(() => requestedCategories).toContain("limit_down");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);

    await page.getByText("风向标", { exact: true }).click();
    await expect(page.getByRole("heading", { name: "风向标", exact: true })).toBeVisible();
    await expect(page.getByText("亿嘉和", { exact: true })).toBeVisible();
    await expect(page.getByText("涨停原因", { exact: true }).first()).toBeVisible();
    await expect.poll(() => requestedCategories).toContain("wind_vane");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  });
}
