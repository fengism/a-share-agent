import { expect, test, type Page } from "./base";

const user = { id: 9, username: "watchlist-tester", is_admin: false, must_change_password: false };

const watchlist = {
  source: "tencent",
  quoted_at: "2026-11-07 10:05:00",
  items: [
    {
      id: 1,
      stock_code: "600519",
      market: "cn",
      stock_name: "贵州茅台",
      note: "高端白酒主线",
      created_at: "2026-11-01 09:30:00",
      current_price: 1688.0,
      change_pct: 2.35,
      open_price: 1650.0,
      high_price: 1695.0,
      low_price: 1648.0,
      previous_close: 1649.2,
      volume: 3200000,
      amount: 5.4e9,
      turnover_pct: 12.5,
      pe_ttm: 28.4,
      market_cap: 2.1e12,
      quote_source: "tencent",
      concepts: [{ code: "BK0477", name: "白酒" }],
      alerts: [],
    },
    {
      id: 2,
      stock_code: "00700",
      market: "hk",
      stock_name: "腾讯控股",
      note: "港股互联网",
      created_at: "2026-11-02 09:30:00",
      current_price: 412.6,
      change_pct: -1.18,
      open_price: 416.0,
      high_price: 418.2,
      low_price: 410.4,
      previous_close: 417.5,
      volume: 18000000,
      amount: 7.4e9,
      turnover_pct: 0.19,
      pe_ttm: 18.2,
      market_cap: 3.9e12,
      quote_source: "tencent",
      concepts: [{ code: "HK-INT", name: "互联网平台" }],
      alerts: [],
    },
  ],
};

async function mockWatchlist(page: Page) {
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\//, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === "/api/auth/me") return route.fulfill({ json: user });
    if (pathname === "/api/watchlist") return route.fulfill({ json: watchlist });
    return route.fulfill({ json: [] });
  });
}

for (const width of [1440, 390]) {
  test(`watchlist renders tracked stocks at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 });
    await mockWatchlist(page);

    await page.goto("/watchlist");

    await expect(page.getByText("WATCHLIST · 自选观察")).toBeVisible();
    await expect(page.getByRole("heading", { name: "我的自选" })).toBeVisible();
    await expect(page.getByText("贵州茅台").first()).toBeVisible();
    await expect(page.getByRole("button", { name: "AI 诊断自选池" })).toBeVisible();
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1),
    ).toBe(true);
  });
}

test("watchlist card layout keeps its migrated styles at 390px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 900 });
  await mockWatchlist(page);

  await page.goto("/watchlist");
  await page.locator(".ant-segmented-item", { hasText: "卡片" }).click();

  const card = page.locator(".watchlist-mobile-card").first();
  await expect(card).toBeVisible();
  await expect(card.getByText("贵州茅台")).toBeVisible();

  const styles = await card.evaluate((el) => {
    const read = (node: Element | null, props: string[]) =>
      node
        ? Object.fromEntries(
            props.map((p) => [p, window.getComputedStyle(node).getPropertyValue(p)]),
          )
        : null;
    const q = (sel: string) => el.querySelector(sel);
    const price = q(".watchlist-mobile-card__price");
    const muted = q(".u-text-muted");
    const body = q(".watchlist-mobile-card__metrics");
    return {
      card: read(el, ["display", "flex-direction", "gap", "border-radius"]),
      tag: read(q(".watchlist-mobile-card__tag"), ["font-size", "margin-inline-end"]),
      price: read(price, ["font-size", "font-weight", "padding-left", "padding-right"]),
      priceColor: price ? window.getComputedStyle(price).color : null,
      name: read(q(".watchlist-mobile-card__name"), ["font-size"]),
      metrics: read(body, ["display", "font-size"]),
      bodyColor: body ? window.getComputedStyle(body).color : null,
      mutedColor: muted ? window.getComputedStyle(muted).color : null,
      concept: read(q(".watchlist-mobile-card__concept"), ["font-size", "border-radius"]),
      mutedCount: el.querySelectorAll(".u-text-muted").length,
    };
  });

  expect(styles.card).toMatchObject({ display: "flex", "flex-direction": "column", gap: "8px", "border-radius": "8px" });
  expect(styles.tag).toEqual({ "font-size": "10px", "margin-inline-end": "0px" });
  expect(styles.price).toMatchObject({
    "font-size": "16px",
    "font-weight": "700",
    "padding-left": "4px",
    "padding-right": "4px",
  });
  expect(styles.name).toMatchObject({ "font-size": "16px" });
  expect(styles.metrics).toMatchObject({ display: "grid", "font-size": "11px" });
  expect(styles.concept).toMatchObject({ "font-size": "10px", "border-radius": "3px" });
  expect(styles.mutedCount).toBe(3);
  expect(styles.mutedColor).not.toBe(styles.bodyColor);
  expect(styles.priceColor).not.toBe(styles.bodyColor);
});
