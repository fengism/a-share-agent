import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import PortfolioSummaryCards from "./PortfolioSummaryCards";

describe("PortfolioSummaryCards", () => {
  it("shows realized, unrealized, and combined profit separately", () => {
    render(
      <PortfolioSummaryCards summary={{
        base_currency: "CNY",
        fx_rates: { CNY: 1 },
        stock_count: 1,
        position_count: 1,
        transaction_count: 2,
        total_cost: 606,
        priced_cost: 606,
        total_market_value: 660,
        total_profit_amount: 54,
        total_profit_pct: 8.91,
        unrealized_profit_amount: 54,
        realized_profit_amount: 74,
        combined_profit_amount: 128,
        profitable_count: 1,
        losing_count: 0,
        unpriced_count: 0,
        cash_configured: true,
        initial_cash: 100000,
        cash_balance: 99394,
        estimated_securities_value: 660,
        total_asset_value: 100054,
        total_position_pct: 0.66,
        previous_close_value: 630,
        daily_profit_amount: 30,
        daily_profit_pct: 4.76,
      }} />,
    );

    expect(screen.getByText("浮动盈亏")).toBeInTheDocument();
    expect(screen.getByText("已实现盈亏")).toBeInTheDocument();
    expect(screen.getByText("综合盈亏")).toBeInTheDocument();
    expect(screen.getByText("按 FIFO 成本核算卖出")).toBeInTheDocument();
    expect(screen.getByText("共 2 笔交易流水")).toBeInTheDocument();
    expect(screen.getByText("总资产").closest(".ant-statistic")).toHaveTextContent("100,054.00");
    expect(screen.getByText("现金余额").closest(".ant-statistic")).toHaveTextContent("99,394.00");
    expect(screen.getByText("总仓位").closest(".ant-statistic")).toHaveTextContent("0.66%");
    expect(screen.getByText("当日盈亏").closest(".ant-statistic")).toHaveTextContent("30.00");
    expect(screen.getByText(/昨收市值 ¥630.00 · 4.76%/)).toBeInTheDocument();
  });

  it("prompts for initial cash when account accounting is not configured", () => {
    render(<PortfolioSummaryCards summary={{
      base_currency: "CNY",
      fx_rates: { CNY: 1 },
      stock_count: 0,
      position_count: 0,
      transaction_count: 0,
      total_cost: 0,
      priced_cost: 0,
      total_market_value: 0,
      total_profit_amount: 0,
      total_profit_pct: null,
      unrealized_profit_amount: 0,
      realized_profit_amount: 0,
      combined_profit_amount: 0,
      profitable_count: 0,
      losing_count: 0,
      unpriced_count: 0,
      cash_configured: false,
      initial_cash: null,
      cash_balance: null,
      estimated_securities_value: 0,
      total_asset_value: null,
      total_position_pct: null,
      previous_close_value: 0,
      daily_profit_amount: 0,
      daily_profit_pct: null,
    }} />);

    expect(screen.getByText("尚未配置初始资金")).toBeInTheDocument();
  });
});
