import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WatchlistAllocationBar } from "./WatchlistAllocationBar";
import type { WatchlistItem } from "../../../types/watchlist";

const mockItems: WatchlistItem[] = [
  {
    id: 1,
    stock_code: "600519",
    stock_name: "贵州茅台",
    note: "",
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
    concepts: [{ code: "BK0896", name: "白酒概念" }],
    alerts: [],
  },
  {
    id: 2,
    stock_code: "300750",
    stock_name: "宁德时代",
    note: "",
    created_at: "2026-08-21T10:00:00",
    current_price: 240,
    change_pct: 2.5,
    open_price: 235,
    high_price: 242,
    low_price: 233,
    previous_close: 234.1,
    volume: 5000000,
    amount: 1200000000,
    turnover_pct: 1.2,
    pe_ttm: 25.0,
    market_cap: 1000000000000,
    quote_source: "tencent",
    concepts: [{ code: "BK0900", name: "动力电池" }],
    alerts: [],
  },
];

describe("WatchlistAllocationBar", () => {
  it("renders allocation legend and handles clicking a concept", () => {
    const onSelect = vi.fn();
    render(
      <WatchlistAllocationBar
        items={mockItems}
        activeConcept="all"
        onSelectConcept={onSelect}
      />,
    );

    expect(screen.getByText("组合概念暴露分布")).toBeInTheDocument();
    expect(screen.getByText("主线 · 白酒概念")).toBeInTheDocument();
    expect(screen.getByText("主线 · 动力电池")).toBeInTheDocument();

    fireEvent.click(screen.getByText("主线 · 白酒概念"));
    expect(onSelect).toHaveBeenCalledWith("白酒概念");
  });

  it("returns null when items is empty", () => {
    const { container } = render(
      <WatchlistAllocationBar
        items={[]}
        activeConcept="all"
        onSelectConcept={vi.fn()}
      />,
    );
    expect(container.firstChild).toBeNull();
  });
});
