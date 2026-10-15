import { expect, test, type Page } from "@playwright/test";

const user = { id: 7, username: "researcher", is_admin: false, must_change_password: false };

/** 首页中间模块（市场看板 / 市场风向 / 今日主线）数据充足时，移动端不得横向溢出。 */
async function mockDashboard(page: Page) {
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\//, async (route) => {
    const path = new URL(route.request().url()).pathname;
    let body: unknown = [];
    if (path === "/api/auth/me") body = user;
    else if (path === "/api/market/indices") body = { source: "腾讯", indices: Array.from({ length: 6 }, (_, i) => ({ code: ["000001", "399001", "399006", "000688", "000300", "000905"][i], name: ["上证指数", "深证成指", "创业板指", "科创50", "沪深300", "中证500"][i], price: 3200 + i * 100, change_pct: i % 2 ? -0.5 : 0.8, amount: 100000000 + i })) };
    else if (path === "/api/market/emotion") body = { source: "财联社", fetched_at: "2026-08-21T10:00:00", market_degree: 62, shsz_balance: "1.2万亿", shsz_balance_change_px: "+120亿", preview_balance: "1.1万亿", preview_balance_change_px: "-10亿", up_ratio: "60%", up_ratio_num: 3000, up_open_num: 2800, performance: "偏强", up_open_ratio: "55%", profit_ratio: "48%", up_down_dis: { status: true, suspend_num: 10, up_num: 3000, down_num: 1800, rise_num: 2900, fall_num: 1700, flat_num: 200, down_10: 5, down_8: 8, down_6: 10, down_4: 20, down_2: 60, up_2: 80, up_4: 50, up_6: 30, up_8: 20, up_10: 12 }, limit_up_board: [{ name: "首板", count: 50, promotion_rate: "20%" }, { name: "2连板", count: 10, promotion_rate: "30%" }] };
    else if (path === "/api/market/limit-up-ladder") body = { source: "开盘红", date: "2026-08-21", fetched_at: "2026-08-21T10:00:00", total: 6, stocks: Array.from({ length: 6 }, (_, i) => ({ code: `60000${i}`, name: `涨停股${i}`, board_count: i + 1, limit_up_time: "09:35", sector_code: "881169", sector_name: "贵金属板块名称很长很长", one_word: false, popular: true, sector_limit_up_count: 5, amount: 100000000, sector_amount: 200000000 })), sectors: Array.from({ length: 4 }, (_, i) => ({ sector_code: `88116${i}`, sector_name: `板块名称${i}`, stock_count: 5, amount: 100000000, stock_codes: ["600000"] })) };
    else if (path === "/api/market/industry-rankings") body = { source: "开盘红", date: "2026-08-21", fetched_at: "2026-08-21T08:00:00+00:00", fund_data_available: true, total: 1, sectors: [{ rank: 1, name: "贵金属", change_pct: 5.338, code: "881169", up_count: null, down_count: null, leader: "", leader_change: null, amount: 47051213914, net_inflow: 3885676376, buy_amount: 19932149027, sell_amount: -16046472651, turnover_rate: 1.526, market_cap: 1354185084652, avg_change: 3.79 }] };
    else if (path === "/api/market/hot-rank/ths/concept") body = Array.from({ length: 6 }, (_, i) => ({ rank: i + 1, code: `BK${i}`, name: `概念板块名称${i}`, change_pct: 2.5, hot_value: 1000 - i, hot_tag: "", tag: "" }));
    else if (path === "/api/market/hot-rank/ths") body = Array.from({ length: 10 }, (_, i) => ({ rank: i + 1, code: `60000${i}`, name: `热股名称${i}`, change_pct: 1.5, hot_value: 999 - i, concept_tag: "概念标签", pop_tag: "" }));
    else if (path === "/api/market/today-wind") body = { source: "财联社", fetched_at: "2026-08-21T10:00:00", items: Array.from({ length: 6 }, (_, i) => ({ plate_code: `p${i}`, plate_name: `风口板块${i}`, catalyst: "催化剂说明文字" })) };
    else if (path.startsWith("/api/market/today-wind/")) body = { source: "财联社", fetched_at: "2026-08-21T10:00:00", plate_code: "p0", items: Array.from({ length: 8 }, (_, i) => ({ code: `60000${i}`, name: `龙头股${i}`, price: 10 + i, change_pct: 5.5, limit_up_days: i % 3 })) };
    else if (path === "/api/market/mainline") body = { source: "财联社", fetched_at: "2026-08-21T10:00:00", style: { title: "风格偏向成长", interpret: "说明文字", indexes: [{ code: "000300", name: "沪深300", change_30d: 3.2, stocks: [{ code: "600000", name: "个股A", change_30d: 5.1 }] }] }, items: [{ title: "人形机器人", description: "描述文字", continued_days: 3, hot: 88, plates: [{ code: "p1", name: "机器人", reason: "逻辑说明", rise_count: 20, change_pct: 4.2, article_title: "", faucets: [{ code: "600001", name: "龙头A", change_pct: 9.9, reason: "逻辑" }] }] }] };
    else if (path === "/api/watchlist") body = { source: "tencent", quoted_at: "2026-08-21T10:00:00", items: Array.from({ length: 5 }, (_, i) => ({ id: i + 1, stock_code: `60000${i}`, stock_name: `自选股票${i}`, note: "", created_at: "2026-08-21T09:00:00", current_price: 10 + i, change_pct: 0.5, quote_source: "tencent", alerts: [] })) };
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
  });
}

/** 返回视口外溢、且不在可横向滚动容器内的元素。 */
async function overflowingElements(page: Page) {
  return page.evaluate(() => {
    const vw = window.innerWidth;
    const insideScroller = (el: Element) => {
      let node: Element | null = el.parentElement;
      while (node && node !== document.body) {
        const style = getComputedStyle(node);
        if (style.overflowX === "auto" || style.overflowX === "scroll") return true;
        node = node.parentElement;
      }
      return false;
    };
    const offenders: string[] = [];
    document.querySelectorAll("body *").forEach((el) => {
      const rect = el.getBoundingClientRect();
      if ((rect.width > vw + 1 || rect.right > vw + 1) && !insideScroller(el)) {
        offenders.push(`${el.tagName}.${String(el.className).split(" ").slice(0, 2).join(".")} (${Math.round(rect.width)}px)`);
      }
    });
    return offenders;
  });
}

for (const width of [360, 390, 414]) {
  test(`keeps the dashboard middle modules within ${width}px`, async ({ page }) => {
    await mockDashboard(page);
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/");

    await expect(page.getByRole("region", { name: "首页中间内容" })).toBeVisible();
    await expect(page.getByText("风口板块0", { exact: true })).toBeVisible();
    await expect(page.getByText("人形机器人", { exact: true })).toBeVisible();

    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    expect(await overflowingElements(page)).toEqual([]);
  });
}
