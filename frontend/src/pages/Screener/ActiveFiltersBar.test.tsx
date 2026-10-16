import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DEFAULT_SCREENER_FILTERS } from "../../features/screener/screenerUrlState";
import type { ScreenerFilter } from "../../types/stock";
import ActiveFiltersBar from "./ActiveFiltersBar";

describe("ActiveFiltersBar", () => {
  const baseFilters: ScreenerFilter = {
    ...DEFAULT_SCREENER_FILTERS,
    pe_min: 0,
    pe_max: 15,
    pb_min: null,
    pb_max: 2,
    markets: ["主板"],
  };

  it("renders active tags and handles single tag removal", () => {
    const onFiltersChange = vi.fn();
    const onSearch = vi.fn();
    const onReset = vi.fn();

    render(
      <ActiveFiltersBar
        filters={baseFilters}
        onFiltersChange={onFiltersChange}
        onSearch={onSearch}
        onReset={onReset}
      />,
    );

    expect(screen.getByText("生效条件 (3)：")).toBeInTheDocument();
    expect(screen.getByText("PE: 0 ~ 15")).toBeInTheDocument();
    expect(screen.getByText("PB ≤ 2")).toBeInTheDocument();
    expect(screen.getByText("板块: 主板")).toBeInTheDocument();

    // Click remove PE
    const closeButtons = screen.getAllByLabelText("Close");
    fireEvent.click(closeButtons[0]);

    expect(onFiltersChange).toHaveBeenCalledWith(
      expect.objectContaining({
        pe_min: null,
        pe_max: null,
        page: 1,
      }),
    );
    expect(onSearch).toHaveBeenCalled();
  });

  it("handles reset all", () => {
    const onReset = vi.fn();

    render(
      <ActiveFiltersBar
        filters={baseFilters}
        onFiltersChange={vi.fn()}
        onSearch={vi.fn()}
        onReset={onReset}
      />,
    );

    const clearButton = screen.getByRole("button", { name: "清空全部" });
    fireEvent.click(clearButton);
    expect(onReset).toHaveBeenCalled();
  });

  it("returns null when no active filters", () => {
    const { container } = render(
      <ActiveFiltersBar
        filters={DEFAULT_SCREENER_FILTERS}
        onFiltersChange={vi.fn()}
        onSearch={vi.fn()}
        onReset={vi.fn()}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders and clears deep value, theme amplitude, and risk tags", () => {
    const onFiltersChange = vi.fn();
    const onSearch = vi.fn();

    render(
      <ActiveFiltersBar
        filters={{
          ...DEFAULT_SCREENER_FILTERS,
          amplitude_min: 5,
          amplitude_max: 15,
          is_broken_net: true,
          exclude_st: true,
          min_amount_yi: 1.0,
        }}
        onFiltersChange={onFiltersChange}
        onSearch={onSearch}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getByText("生效条件 (4)：")).toBeInTheDocument();
    expect(screen.getByText("振幅: 5 ~ 15%")).toBeInTheDocument();
    expect(screen.getByText("仅破净股 (PB≤1.0)")).toBeInTheDocument();
    expect(screen.getByText("剔除ST风险股")).toBeInTheDocument();
    expect(screen.getByText("成交额 ≥ 1亿")).toBeInTheDocument();

    const closeButtons = screen.getAllByLabelText("Close");
    // Remove is_broken_net
    fireEvent.click(closeButtons[1]);
    expect(onFiltersChange).toHaveBeenCalledWith(
      expect.objectContaining({
        is_broken_net: false,
        page: 1,
      }),
    );
    expect(onSearch).toHaveBeenCalled();
  });
});
