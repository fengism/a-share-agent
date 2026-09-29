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
          onSell={vi.fn()}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("已清仓股票")).toBeInTheDocument();
    expect(screen.getByText("1 天")).toBeInTheDocument();
    expect(screen.getAllByText("¥1,010.00").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /贵州茅台/ })[0]).toHaveAttribute(
      "href",
      "/stock/600519",
    );

    const expandButton = container.querySelector<HTMLButtonElement>(".ant-table-row-expand-icon");
    expect(expandButton).not.toBeNull();
    fireEvent.click(expandButton!);

    expect(screen.getAllByText("买入流水").length).toBeGreaterThan(0);
    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getAllByText("含费单位成本").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /编辑 贵州茅台/ })).toBeInTheDocument();
  });

  it("starts a sell from the current holding row", () => {
    const handleSell = vi.fn();
    render(
      <MemoryRouter>
        <PortfolioTables
          positions={[]}
          stocks={[{
            stock_code: "600519",
            stock_name: "贵州茅台",
            position_count: 1,
            total_shares: 60,
            average_cost: 10.1,
            current_price: 11,
            change_pct: 1,
            cost_value: 606,
            market_value: 660,
            profit_amount: 54,
            profit_pct: 8.91,
            realized_profit_amount: 74,
            total_profit_amount: 128,
          }]}
          closedPositions={[]}
          transactions={[]}
          onSell={handleSell}
        />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: "卖出 贵州茅台" }));

    expect(handleSell).toHaveBeenCalledWith(expect.objectContaining({
      stock_code: "600519",
      total_shares: 60,
    }));
  });

  it("supports exporting holdings to CSV and navigating to report analysis", () => {
    window.URL.createObjectURL = vi.fn(() => "blob:mock-url");
    window.URL.revokeObjectURL = vi.fn();
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    render(
      <MemoryRouter>
        <PortfolioTables
          positions={[]}
          stocks={[{
            stock_code: "600519",
            stock_name: "贵州茅台",
            position_count: 1,
            total_shares: 60,
            average_cost: 10.1,
            current_price: 11,
            change_pct: 1,
            cost_value: 606,
            market_value: 660,
            profit_amount: 54,
            profit_pct: 8.91,
            realized_profit_amount: 74,
            total_profit_amount: 128,
          }]}
          closedPositions={[]}
          transactions={[]}
          onSell={vi.fn()}
        />
      </MemoryRouter>,
    );

    const exportBtn = screen.getByRole("button", { name: /导出 CSV/ });
    expect(exportBtn).toBeInTheDocument();
    fireEvent.click(exportBtn);
    expect(window.URL.createObjectURL).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
    clickSpy.mockRestore();

    expect(screen.getByRole("link", { name: "查看贵州茅台研报" })).toHaveAttribute("href", "/analysis?code=600519");
  });
});
