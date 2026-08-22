import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import PortfolioSummaryCards from "./PortfolioSummaryCards";

describe("PortfolioSummaryCards", () => {
  it("shows realized, unrealized, and combined profit separately", () => {
    render(
      <PortfolioSummaryCards summary={{
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
      }} />,
    );

    expect(screen.getByText("浮动盈亏")).toBeInTheDocument();
    expect(screen.getByText("已实现盈亏")).toBeInTheDocument();
    expect(screen.getByText("综合盈亏")).toBeInTheDocument();
    expect(screen.getByText("按 FIFO 成本核算卖出")).toBeInTheDocument();
    expect(screen.getByText("共 2 笔交易流水")).toBeInTheDocument();
  });
});
