import { act, createRef } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import TransactionEntryCard, { type TransactionEntryCardHandle } from "./TransactionEntryCard";

const mocks = vi.hoisted(() => ({
  createTransaction: vi.fn(),
  previewTransaction: vi.fn(),
  resetPreview: vi.fn(),
}));

vi.mock("../../api/queries", () => ({
  useCreatePortfolioTransaction: () => ({
    mutateAsync: mocks.createTransaction,
    isPending: false,
  }),
  usePreviewPortfolioTransaction: () => ({
    mutateAsync: mocks.previewTransaction,
    isPending: false,
    data: undefined,
    reset: mocks.resetPreview,
  }),
}));

vi.mock("../../hooks/useStockSearchController", () => ({
  useStockSearchController: () => ({
    inputValue: "",
    normalizedInput: "",
    currentResults: [],
    isPending: false,
    isError: false,
    error: null,
    retry: vi.fn(),
    setInputValue: vi.fn(),
    clear: vi.fn(),
    resolveCode: vi.fn(),
  }),
}));

describe("TransactionEntryCard", () => {
  beforeEach(() => {
    mocks.createTransaction.mockReset().mockResolvedValue({ id: 9 });
    mocks.previewTransaction.mockReset();
    mocks.resetPreview.mockReset();
  });

  it("limits sell entry to held stocks and submits the selected holding", async () => {
    render(
      <TransactionEntryCard stocks={[{
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
      }]} />,
    );

    fireEvent.click(screen.getByRole("radio", { name: "卖出" }));
    fireEvent.mouseDown(await screen.findByRole("combobox", { name: "持仓股票" }));
    fireEvent.click(await screen.findByText(/贵州茅台.*可卖 60 股/));
    fireEvent.change(screen.getByRole("spinbutton", { name: "卖出价" }), { target: { value: "12" } });
    fireEvent.change(screen.getByRole("spinbutton", { name: /股数/ }), { target: { value: "40" } });
    fireEvent.click(screen.getByRole("button", { name: /记录卖出/ }));

    await waitFor(() => expect(mocks.createTransaction).toHaveBeenCalledTimes(1));
    expect(mocks.createTransaction).toHaveBeenCalledWith(expect.objectContaining({
      stock_code: "600519",
      side: "sell",
      trade_price: 12,
      shares: 40,
      fee: 0,
      note: "",
    }));
  });

  it("previews a sell with the same transaction payload", async () => {
    mocks.previewTransaction.mockResolvedValue({
      available_shares: 60,
      shares_after_trade: 20,
      current_shares_after: 20,
      matched_cost: 404,
      realized_profit_amount: 74,
      matches: [],
    });
    render(
      <TransactionEntryCard stocks={[{
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
      }]} />,
    );

    fireEvent.click(screen.getByRole("radio", { name: "卖出" }));
    fireEvent.mouseDown(await screen.findByRole("combobox", { name: "持仓股票" }));
    fireEvent.click(await screen.findByText(/贵州茅台.*可卖 60 股/));
    fireEvent.change(screen.getByRole("spinbutton", { name: "卖出价" }), { target: { value: "12" } });
    fireEvent.change(screen.getByRole("spinbutton", { name: /股数/ }), { target: { value: "40" } });
    fireEvent.click(screen.getByRole("button", { name: /预演卖出/ }));

    await waitFor(() => expect(mocks.previewTransaction).toHaveBeenCalledTimes(1));
    expect(mocks.previewTransaction).toHaveBeenCalledWith(expect.objectContaining({
      stock_code: "600519",
      side: "sell",
      trade_price: 12,
      shares: 40,
      fee: 0,
      note: "",
    }));
  });

  it("opens a selected holding for sale and prefills its current price", async () => {
    const ref = createRef<TransactionEntryCardHandle>();
    const stock = {
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
    };
    render(<TransactionEntryCard ref={ref} stocks={[stock]} />);

    act(() => ref.current?.startSell(stock));

    await waitFor(() => expect(screen.getByRole("radio", { name: "卖出" })).toBeChecked());
    expect(screen.getByRole("combobox", { name: "持仓股票" })).toBeInTheDocument();
    expect(screen.getByText(/贵州茅台.*可卖 60 股/)).toBeInTheDocument();
    expect(screen.getByRole("spinbutton", { name: "卖出价" })).toHaveValue("11.0000");
  });
});
