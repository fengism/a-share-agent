import { expect, test, type Page } from "./base";

const user = {
  id: 7,
  username: "tester",
  is_admin: false,
  must_change_password: false,
};

const portfolioPayload = {
  positions: [
    {
      id: 1,
      stock_code: "600519",
      stock_name: "贵州茅台",
      buy_price: 1500,
      buy_time: "2026-01-02T09:30:00",
      shares: 100,
      current_price: 1650,
      change_pct: 2.1,
      cost_value: 150000,
      market_value: 165000,
      profit_amount: 15000,
      profit_pct: 10.0,
    },
  ],
  stocks: [
    {
      stock_code: "600519",
      stock_name: "贵州茅台",
      position_count: 1,
      total_shares: 100,
      average_cost: 1500,
      current_price: 1650,
      change_pct: 2.1,
      cost_value: 150000,
      market_value: 165000,
      profit_amount: 15000,
      profit_pct: 10.0,
      realized_profit_amount: 3200,
      total_profit_amount: 18200,
      allocation_pct: 66.0,
    },
  ],
  transactions: [
    {
      id: 10,
      stock_code: "600519",
      stock_name: "贵州茅台",
      side: "buy",
      trade_price: 1500,
      trade_time: "2026-01-02T09:30:00",
      shares: 100,
      fee: 5,
      note: "建仓",
      created_at: "2026-01-02T09:30:00",
    },
  ],
  closed_positions: [],
  summary: {
    stock_count: 1,
    position_count: 1,
    transaction_count: 1,
    total_cost: 150000,
    priced_cost: 150000,
    total_market_value: 165000,
    estimated_securities_value: 165000,
    previous_close_value: 161600,
    daily_profit_amount: 3400,
    daily_profit_pct: 2.1,
    total_profit_amount: 15000,
    total_profit_pct: 10.0,
    unrealized_profit_amount: 15000,
    realized_profit_amount: 3200,
    combined_profit_amount: 18200,
    profitable_count: 1,
    losing_count: 0,
    unpriced_count: 0,
    cash_configured: true,
    initial_cash: 235000,
    cash_balance: 85000,
    total_asset_value: 250000,
    total_position_pct: 66.0,
  },
  risk: {
    largest_position_stock_code: "600519",
    largest_position_stock_name: "贵州茅台",
    max_single_stock_pct: 66.0,
    top3_concentration_pct: 66.0,
    top5_concentration_pct: 100.0,
    effective_holding_count: 1.8,
    concentration_index: 5512,
    cash_pct: 34.0,
    securities_top5_concentration_pct: 100.0,
    securities_effective_holding_count: 1.0,
    securities_concentration_index: 10000,
    remaining_add_capacity: 35000,
    concentration_level: "high",
    priced_stock_count: 1,
    unpriced_stock_count: 0,
    max_total_position_limit_pct: 80,
    max_single_stock_limit_pct: 30,
    max_sector_limit_pct: 40,
    largest_sector_name: "白酒",
    largest_sector_pct: 66.0,
    sector_allocations: [{ sector_name: "白酒", market_value: 165000, allocation_pct: 66.0, stock_count: 1 }],
    trim_suggestions: [],
    warnings: ["单一股票仓位占比较高"],
  },
  settings: {
    initial_cash: 235000,
    max_total_position_pct: 80,
    max_single_stock_pct: 30,
    max_sector_pct: 40,
  },
  quoted_at: "2026-01-03T10:00:00",
  quote_source: "tencent",
  quote_stale: false,
};

const equityCurvePayload = {
  mode: "total_assets",
  start_date: "2026-01-02",
  end_date: "2026-01-03",
  current_total_assets: 250000,
  current_securities_value: 165000,
  total_return_pct: 6.38,
  annualized_return_pct: 18.5,
  annualized_volatility_pct: 12.4,
  max_drawdown_pct: 2.1,
  sharpe_ratio: 1.32,
  calmar_ratio: 8.81,
  win_rate_pct: 60.0,
  best_day_pct: 2.1,
  worst_day_pct: -0.8,
  longest_drawdown_days: 2,
  trading_days: 2,
  risk_free_rate_pct: 1.5,
  warnings: [],
  points: [
    { date: "2026-01-02", total_assets: 235000, securities_value: 150000, cash_balance: 85000, return_pct: 0, benchmark_return_pct: 0 },
    { date: "2026-01-03", total_assets: 250000, securities_value: 165000, cash_balance: 85000, return_pct: 6.38, benchmark_return_pct: 1.2 },
  ],
};

const nationalTeamPayload = {
  as_of_date: "2026-01-03",
  expected_date: "2026-01-03",
  stale: false,
  partial: false,
  refreshing: false,
  calendar_degraded: false,
  covered_etf_count: 2,
  total_etf_count: 2,
  methodology: "ETF 当日份额变化 × ETF 当日收盘价，逐只计算后按宽基汇总。",
  summary: {
    total_shares_100m: 3200.5,
    total_amount_1d_100m: 185.4,
    estimated_net_flow_1d_100m: 42.6,
    estimated_net_flow_5d_100m: 128.0,
    estimated_net_flow_20d_100m: 360.2,
    cumulative_net_flow_100m: 512.8,
    ytd_net_flow_100m: 42.6,
    change_1d_100m: 12.4,
    change_5d_100m: 38.2,
    change_20d_100m: 105.0,
    quality: "complete",
  },
  support_score: {
    score: 74,
    status: "strong",
    label: "强力托底",
    updated_at: "2026-01-03T15:00:00",
    dimensions: {
      flow_intensity: 80,
      volume_anomaly: 78,
      breadth_diffusion: 70,
      dip_buying: 72,
      persistence: 68,
    },
  },
  support_score_history: [
    { date: "2026-01-02", score: 58, benchmark_close: 3210 },
    { date: "2026-01-03", score: 74, benchmark_close: 3190 },
  ],
  daily_flows: [
    { date: "2026-01-01", total_flow_100m: 12.0, benchmark_close: 3220, by_index: { hs300: 10.0, zz500: 2.0 } },
    { date: "2026-01-02", total_flow_100m: 18.5, benchmark_close: 3210, by_index: { hs300: 14.5, zz500: 4.0 } },
    { date: "2026-01-03", total_flow_100m: 42.6, benchmark_close: 3190, by_index: { hs300: 35.6, zz500: 7.0 } },
  ],
  indices: [
    {
      index_key: "hs300",
      index_code: "000300.SH",
      index_name: "沪深300",
      category: "core",
      etf_count: 1,
      latest_shares_100m: 2600.0,
      latest_change_1d_100m: 10.2,
      change_5d_100m: 30.0,
      change_20d_100m: 85.0,
      estimated_net_flow_1d_100m: 35.6,
      estimated_net_flow_5d_100m: 102.0,
      estimated_net_flow_20d_100m: 290.0,
      points: [],
    },
  ],
  etfs: [
    {
      code: "510300",
      name: "沪深300ETF",
      fund_company: "华泰柏瑞",
      index_key: "hs300",
      index_code: "000300.SH",
      index_name: "沪深300",
      category: "core",
      latest_date: "2026-01-03",
      latest_shares_100m: 2600.0,
      latest_close: 3.92,
      latest_change_pct: -0.51,
      latest_amount_100m: 98.5,
      volume_ratio: 2.4,
      is_abnormal_volume: true,
      change_1d_100m: 10.2,
      change_5d_100m: 30.0,
      change_20d_100m: 85.0,
      estimated_net_flow_1d_100m: 35.6,
      estimated_net_flow_5d_100m: 102.0,
      estimated_net_flow_20d_100m: 290.0,
      points: [],
    },
  ],
  intraday: {
    date: "2026-01-03",
    minute: {
      pre_close: 3210,
      slots: ["09:30", "09:31", "09:32"],
      bars: [12.5, 18.2, 25.4],
      closes: [3205, 3198, 3190],
    },
    cumulative: {
      slots: ["09:30", "09:31", "09:32"],
      prev: [10.0, 20.0, 32.0],
      avg20: [9.5, 18.5, 28.0],
    },
    items: [
      {
        code: "510300",
        name: "沪深300ETF",
        price: 3.92,
        pct: -0.51,
        amount: 98.5,
      },
    ],
  },
};

async function setupRoutes(page: Page) {
  await page.route(/^http:\/\/127\.0\.0\.1:4173\/api\//, async (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname === "/api/auth/me") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(user) });
      return;
    }
    if (pathname === "/api/portfolio") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(portfolioPayload) });
      return;
    }
    if (pathname === "/api/portfolio/equity-curve") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(equityCurvePayload) });
      return;
    }
    if (pathname === "/api/market/national-team-etf-holdings") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(nationalTeamPayload) });
      return;
    }
    if (pathname === "/api/market/national-team/backtest") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [], summary: null }) });
      return;
    }
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
  });
}

for (const viewport of [
  { width: 1440, height: 900, label: "1440px" },
  { width: 560, height: 844, label: "560px" },
  { width: 390, height: 844, label: "390px" },
]) {
  test(`renders portfolio summary, risk, and equity metrics at ${viewport.label}`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await setupRoutes(page);
    await page.goto("/portfolio");
    await expect(page.getByRole("heading", { name: "仓位管理" })).toBeVisible();
    await expect(page.getByText("最大单股权重")).toBeVisible();
    await expect(page.getByText("期末总资产")).toBeVisible();
  });
}

for (const viewport of [
  { width: 1440, height: 900, label: "1440px" },
  { width: 390, height: 844, label: "390px" },
]) {
  test(`renders national team sweep alert and anomaly banner at ${viewport.label}`, async ({ page }) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await setupRoutes(page);
    await page.goto("/national-team?tab=all");
    await expect(page.getByText("盘中主力放量异动监测")).toBeVisible();
    await expect(page.getByTestId("national-team-anomaly-banner")).toBeVisible();
  });
}
