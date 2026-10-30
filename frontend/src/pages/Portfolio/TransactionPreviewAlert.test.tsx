import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PortfolioTransactionPreview } from "../../types/portfolio";
import TransactionPreviewAlert from "./TransactionPreviewAlert";

function expectSpanText(expected: string) {
  const compactExpected = expected.replace(/\s/g, "");
  expect(screen.getByText((_, element) => (
    element?.tagName === "SPAN"
    && (element.textContent ?? "").replace(/\s/g, "").includes(compactExpected)
  ))).toBeInTheDocument();
}

describe("TransactionPreviewAlert", () => {
  it("shows post-buy account allocations and risk warnings", () => {
    const preview: PortfolioTransactionPreview = {
      stock_code: "600519",
      side: "buy",
      currency: "CNY",
      fx_rate_to_cny: 1,
      trade_time: "2026-09-19T10:00:00",
      available_shares: 0,
      shares_after_trade: 100,
      current_shares_after: 100,
      matched_cost: null,
      realized_profit_amount: null,
      matches: [],
      trade_amount: 1000,
      trade_amount_native: 1000,
      fee: 5,
      fee_native: 5,
      cash_balance_after: 8995,
      estimated_total_assets_after: 9995,
      total_position_pct_after: 10.01,
      stock_position_pct_after: 10.01,
      sector_name: "食品饮料",
      sector_position_pct_after: 10.01,
      warnings: ["总仓位超过上限。"],
    };

    render(<TransactionPreviewAlert preview={preview} title="买入预演" />);

    expect(screen.getByText("买入预演")).toBeInTheDocument();
    expectSpanText("买入金额 ¥1,000.00（人民币），手续费 ¥5.00");
    expectSpanText("交易后现金 ¥8,995.00，预计总资产 ¥9,995.00，总仓位 10.01%");
    expectSpanText("单股仓位 10.01%，食品饮料行业仓位 10.01%");
    expectSpanText("A 股 T+1：本次买入的股份当日不可卖出，次一交易日可卖。");
    expectSpanText("风险提示：总仓位超过上限。");
  });

  it("shows FIFO cost and matched buy lots for a sell preview", () => {
    const preview: PortfolioTransactionPreview = {
      stock_code: "600519",
      side: "sell",
      currency: "CNY",
      fx_rate_to_cny: 1,
      trade_time: "2026-09-19T10:00:00",
      available_shares: 100,
      shares_after_trade: 60,
      current_shares_after: 60,
      matched_cost: 404,
      realized_profit_amount: 74,
      matches: [{
        buy_transaction_id: 7,
        currency: "CNY",
        buy_time: "2026-09-01T09:30:00",
        buy_price: 10,
        shares: 40,
        unit_cost: 10.1,
        matched_cost: 404,
      }],
      trade_amount: 480,
      trade_amount_native: 480,
      fee: 2,
      fee_native: 2,
      cash_balance_after: 9478,
      estimated_total_assets_after: 10078,
      total_position_pct_after: 5.95,
      stock_position_pct_after: 5.95,
      sector_name: "食品饮料",
      sector_position_pct_after: 5.95,
      warnings: [],
    };

    render(<TransactionPreviewAlert preview={preview} title="卖出预演" />);

    expectSpanText("FIFO 匹配成本 ¥404.00，预计已实现盈亏 ¥74.00");
    expectSpanText("匹配买入 #7（2026-09-01 09:30，¥10.00 × 40 股，成本 ¥404.00）");
    expectSpanText("交易时点可用 100 股，卖出后剩余 60 股，按当前全部流水回放后剩余 60 股");
  });

  it("shows zero stock allocation and the remaining sector allocation after a full sell", () => {
    const preview: PortfolioTransactionPreview = {
      stock_code: "600519",
      side: "sell",
      currency: "CNY",
      fx_rate_to_cny: 1,
      trade_time: "2026-09-19T10:00:00",
      available_shares: 100,
      shares_after_trade: 0,
      current_shares_after: 0,
      matched_cost: 1000,
      realized_profit_amount: 0,
      matches: [],
      trade_amount: 1000,
      trade_amount_native: 1000,
      fee: 0,
      fee_native: 0,
      cash_balance_after: 9000,
      estimated_total_assets_after: 10000,
      total_position_pct_after: 10,
      stock_position_pct_after: 0,
      sector_name: "食品饮料",
      sector_position_pct_after: 10,
      warnings: [],
    };

    render(<TransactionPreviewAlert preview={preview} title="清仓预演" />);

    expectSpanText("单股仓位 0.00%，食品饮料行业仓位 10.00%");
  });

});
