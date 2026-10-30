import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { PortfolioStockSummary, PortfolioTransaction } from "../../types/portfolio";
import PortfolioTradeKline from "./PortfolioTradeKline";

const mocks = vi.hoisted(() => ({ useKlineData: vi.fn() }));

vi.mock("../../api/queries", () => ({ useKlineData: mocks.useKlineData }));
vi.mock("../../hooks/useMediaQuery", () => ({ useMediaQuery: () => false }));
vi.mock("../../charts/LazyKlineChart", () => ({
  default: ({ tradeMarkers }: { tradeMarkers: unknown }) => (
    <div data-testid="portfolio-trade-kline" data-markers={JSON.stringify(tradeMarkers)} />
  ),
}));

const stocks: PortfolioStockSummary[] = [{
  stock_code: "600519",
  stock_name: "贵州茅台",
  currency: "CNY",
  fx_rate_to_cny: 1,
  position_count: 1,
  total_shares: 100,
  average_cost: 10.01,
  current_price: 12,
  cost_value: 1001,
  realized_profit_amount: 0,
}];

const transactions: PortfolioTransaction[] = [{
  id: 1,
  stock_code: "600519",
  stock_name: "贵州茅台",
  side: "buy",
  currency: "CNY",
  fx_rate_to_cny: 1,
  trade_price: 10,
  trade_time: "2026-01-02T09:31:00",
  shares: 100,
  fee: 1,
  fee_native: 1,
  trade_amount: 1000,
  trade_amount_native: 1000,
  note: "首次建仓",
  created_at: "2026-01-02T09:32:00",
}, {
  id: 2,
  stock_code: "600519",
  stock_name: "贵州茅台",
  side: "sell",
  currency: "CNY",
  fx_rate_to_cny: 1,
  trade_price: 12,
  trade_time: "2026-01-05T14:50:00",
  shares: 40,
  fee: 2,
  fee_native: 2,
  trade_amount: 480,
  trade_amount_native: 480,
  note: "部分止盈",
  created_at: "2026-01-05T14:51:00",
}];

describe("PortfolioTradeKline", () => {
  it("renders B/S points and exact real-trade details on an unadjusted K-line", () => {
    mocks.useKlineData.mockReturnValue({
      data: {
        source: "tencent",
        items: [
          { date: "2026-01-02", open: 9, high: 11, low: 8, close: 10, volume: 100, amount: 1000 },
          { date: "2026-01-05", open: 11, high: 13, low: 10, close: 12, volume: 100, amount: 1200 },
        ],
      },
      isLoading: false,
      error: null,
    });

    render(<PortfolioTradeKline stocks={stocks} transactions={transactions} />);

    expect(screen.getByText("持仓个股实际买卖点")).toBeInTheDocument();
    expect(screen.getByText("B 买入")).toBeInTheDocument();
    expect(screen.getByText("S 卖出")).toBeInTheDocument();
    expect(screen.getByTestId("portfolio-trade-kline")).toHaveAttribute(
      "data-markers",
      JSON.stringify([
        { date: "2026-01-02", side: "buy", label: "B ¥10.00" },
        { date: "2026-01-05", side: "sell", label: "S ¥12.00" },
      ]),
    );
    expect(screen.getByText(/2026-01-02 09:31/)).toBeInTheDocument();
    expect(screen.getByText(/100 股/)).toBeInTheDocument();
    expect(screen.getByText(/手续费 ¥1.00/)).toBeInTheDocument();
    expect(screen.getByText(/2026-01-05 14:50/)).toBeInTheDocument();
    expect(mocks.useKlineData).toHaveBeenCalledWith(
      "600519",
      "daily",
      "",
      true,
      expect.objectContaining({ startDate: "20260102" }),
    );
  });

  it("shows an empty state when there is no current holding", () => {
    mocks.useKlineData.mockReturnValue({ data: undefined, isLoading: false, error: null });

    render(<PortfolioTradeKline stocks={[]} transactions={transactions} />);

    expect(screen.getByText("当前没有持仓，暂无实际买卖点")).toBeInTheDocument();
  });
});
