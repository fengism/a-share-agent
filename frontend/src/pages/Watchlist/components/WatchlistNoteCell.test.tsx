import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WatchlistNoteCell } from "./WatchlistNoteCell";
import type { WatchlistItem } from "../../../types/watchlist";

const mockItem: WatchlistItem = {
  id: 1,
  stock_code: "600519",
  stock_name: "贵州茅台",
  note: "白酒核心底仓",
  created_at: "2026-08-20T10:00:00",
  current_price: 1518.2,
  change_pct: 1.26,
  open_price: 1502,
  high_price: 1522.8,
  low_price: 1498.5,
  previous_close: 1499.31,
  volume: 2300000,
  amount: 3480000000,
  turnover_pct: 0.19,
  pe_ttm: 23.45,
  market_cap: 1905000000000,
  quote_source: "tencent",
  concepts: [],
  alerts: [],
};

describe("WatchlistNoteCell", () => {
  it("renders existing note and allows inline editing", async () => {
    const onUpdate = vi.fn().mockResolvedValue(undefined);
    render(<WatchlistNoteCell item={mockItem} onUpdateNote={onUpdate} />);

    expect(screen.getByText("白酒核心底仓")).toBeInTheDocument();

    fireEvent.click(screen.getByText("白酒核心底仓"));
    expect(screen.getByText("编辑 贵州茅台 备注")).toBeInTheDocument();

    const textarea = screen.getByPlaceholderText(/输入跟踪逻辑/);
    fireEvent.change(textarea, { target: { value: "新调整的买入理由" } });

    const saveBtn = screen.getByRole("button", { name: /保\s*存/ });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(onUpdate).toHaveBeenCalledWith("600519", "新调整的买入理由", undefined);
    });
  });

  it("renders add note trigger when note is empty", () => {
    const emptyItem = { ...mockItem, note: "" };
    render(<WatchlistNoteCell item={emptyItem} onUpdateNote={vi.fn()} />);

    expect(screen.getByText("添加")).toBeInTheDocument();
  });
});
