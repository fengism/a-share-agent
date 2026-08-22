import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import PortfolioTables from "./PortfolioTables";

const mocks = vi.hoisted(() => ({
  resetPreview: vi.fn(),
}));

vi.mock("../../api/queries", () => ({
  useDeletePortfolioTransaction: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
    variables: undefined,
  }),
  usePreviewPortfolioTransactionUpdate: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
    data: undefined,
    reset: mocks.resetPreview,
  }),
  useUpdatePortfolioTransaction: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
}));

describe("PortfolioTables", () => {
  it("shows closed positions and expands FIFO lot matches", () => {
    const { container } = render(
      <MemoryRouter>
        <PortfolioTables
          positions={[]}
          stocks={[]}
          closedPositions={[{
            stock_code: "600519",
            stock_name: "贵州茅台",
            transaction_count: 2,
            buy_count: 1,
            sell_count: 1,
            total_shares: 100,
            matched_cost: 1010,
            realized_profit_amount: 188,
            realized_profit_pct: 18.61,
            first_trade_time: "2026-01-02T09:30:00",
            last_trade_time: "2026-01-03T09:30:00",
            holding_days: 1,
          }]}
          transactions={[{
            id: 2,
            stock_code: "600519",
            stock_name: "贵州茅台",
            side: "sell",
            trade_price: 12,
            trade_time: "2026-01-03T09:30:00",
            shares: 100,
            fee: 2,
            note: "清仓",
            created_at: "2026-01-03T09:31:00",
            matched_cost: 1010,
            realized_profit_amount: 188,
            matches: [{
              buy_transaction_id: 1,
              buy_time: "2026-01-02T09:30:00",
              buy_price: 10,
              shares: 100,
              unit_cost: 10.1,
              matched_cost: 1010,
            }],
          }]}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("已清仓股票")).toBeInTheDocument();
    expect(screen.getByText("1 天")).toBeInTheDocument();
    expect(screen.getAllByText("¥1,010.00").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /贵州茅台/ })[0]).toHaveAttribute(
      "href",
      "https://data.eastmoney.com/stockdata/600519.html",
    );

    const expandButton = container.querySelector<HTMLButtonElement>(".ant-table-row-expand-icon");
    expect(expandButton).not.toBeNull();
    fireEvent.click(expandButton!);

    expect(screen.getAllByText("买入流水").length).toBeGreaterThan(0);
    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getAllByText("含费单位成本").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /编辑 贵州茅台/ })).toBeInTheDocument();
  });
});
