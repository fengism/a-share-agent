import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { DEFAULT_SCREENER_FILTERS } from "../../features/screener/screenerUrlState";
import ResultsTable from "./ResultsTable";

describe("ResultsTable", () => {
  it("exposes selected stock codes for batch actions", () => {
    const onSelectedCodesChange = vi.fn();
    render(
      <MemoryRouter>
        <ResultsTable
          data={{
            items: [{
              code: "600519",
              name: "贵州茅台",
              price: 1500,
              change_pct: 1,
              pe_ttm: 20,
              pb: 8,
              market_cap: 18000,
              turnover_pct: 0.5,
              volume: 1000,
              exchange: "SH",
              board: "主板",
              listing_date: "2001-08-27",
              exchange_industry: "制造业",
              second_industry: { code: "801123", name: "白酒Ⅱ" },
            }],
            total: 1,
            page: 1,
            page_size: 50,
          }}
          isLoading={false}
          percentileMap={new Map()}
          showPercentile={false}
          onPageChange={vi.fn()}
          filters={DEFAULT_SCREENER_FILTERS}
          onSortChange={vi.fn()}
          selectedCodes={[]}
          onSelectedCodesChange={onSelectedCodesChange}
          strategySignalDates={new Map([["600519", "2026-08-17"]])}
          strategyDataSources={new Map([["600519", "eastmoney-direct-fallback"]])}
          strategyFallbackCodes={new Set(["600519"])}
        />
      </MemoryRouter>,
    );

    const rowCheckbox = screen.getAllByRole("checkbox")[1];
    fireEvent.click(rowCheckbox);
    expect(onSelectedCodesChange).toHaveBeenCalledWith(["600519"]);
    expect(screen.getByRole("link", { name: "600519" })).toHaveAttribute(
      "href",
      "/analysis/600519",
    );
    expect(screen.getByRole("link", { name: "600519" })).not.toHaveAttribute("target");
    expect(screen.getByText("主板")).toBeInTheDocument();
    expect(screen.getByText("制造业")).toBeInTheDocument();
    expect(screen.getByText("白酒Ⅱ")).not.toHaveClass("ant-tag");
    expect(screen.getAllByText("申万二级").length).toBeGreaterThan(0);
    expect(screen.getAllByText("交易所行业").length).toBeGreaterThan(0);
    expect(screen.getByText("2026-08-17")).toBeInTheDocument();
    expect(screen.getByText("eastmoney-direct-fallback")).toBeInTheDocument();
  });
});
