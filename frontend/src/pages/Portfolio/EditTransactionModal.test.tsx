import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EditTransactionModal from "./EditTransactionModal";

const mocks = vi.hoisted(() => ({
  previewTransaction: vi.fn(),
  resetPreview: vi.fn(),
  updateTransaction: vi.fn(),
}));

vi.mock("../../api/queries", () => ({
  usePreviewPortfolioTransactionUpdate: () => ({
    mutateAsync: mocks.previewTransaction,
    isPending: false,
    data: undefined,
    reset: mocks.resetPreview,
  }),
  useUpdatePortfolioTransaction: () => ({
    mutateAsync: mocks.updateTransaction,
    isPending: false,
  }),
}));

describe("EditTransactionModal", () => {
  beforeEach(() => {
    mocks.previewTransaction.mockReset();
    mocks.resetPreview.mockReset();
    mocks.updateTransaction.mockReset().mockResolvedValue({ id: 2 });
  });

  it("submits the full edited transaction atomically", async () => {
    const onClose = vi.fn();
    render(
      <EditTransactionModal
        transaction={{
          id: 2,
          stock_code: "600519",
          stock_name: "贵州茅台",
          side: "sell",
          trade_price: 12,
          trade_time: "2026-01-03T09:30:00",
          shares: 40,
          fee: 2,
          note: "止盈",
          created_at: "2026-01-03T09:31:00",
          matched_cost: 404,
          realized_profit_amount: 74,
          matches: [],
        }}
        onClose={onClose}
      />,
    );

    fireEvent.change(screen.getByRole("spinbutton", { name: "股数" }), { target: { value: "30" } });
    fireEvent.change(screen.getByRole("textbox", { name: "备注" }), { target: { value: "部分止盈" } });
    fireEvent.click(screen.getByRole("button", { name: "保存修改" }));

    await waitFor(() => expect(mocks.updateTransaction).toHaveBeenCalledTimes(1));
    expect(mocks.updateTransaction).toHaveBeenCalledWith({
      transactionId: 2,
      transaction: expect.objectContaining({
        stock_code: "600519",
        side: "sell",
        trade_price: 12,
        shares: 30,
        fee: 2,
        note: "部分止盈",
      }),
    });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("previews the edited sell as a replacement transaction", async () => {
    mocks.previewTransaction.mockResolvedValue({
      available_shares: 100,
      shares_after_trade: 40,
      current_shares_after: 40,
      matched_cost: 606,
      realized_profit_amount: 112,
      matches: [],
    });
    render(
      <EditTransactionModal
        transaction={{
          id: 2,
          stock_code: "600519",
          stock_name: "贵州茅台",
          side: "sell",
          trade_price: 12,
          trade_time: "2026-01-03T09:30:00",
          shares: 40,
          fee: 2,
          note: "止盈",
          created_at: "2026-01-03T09:31:00",
          matched_cost: 404,
          realized_profit_amount: 74,
          matches: [],
        }}
        onClose={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByRole("spinbutton", { name: "股数" }), { target: { value: "60" } });
    fireEvent.click(screen.getByRole("button", { name: "预演修改" }));

    await waitFor(() => expect(mocks.previewTransaction).toHaveBeenCalledTimes(1));
    expect(mocks.previewTransaction).toHaveBeenCalledWith({
      transactionId: 2,
      transaction: expect.objectContaining({
        stock_code: "600519",
        side: "sell",
        shares: 60,
      }),
    });
  });
});
