import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { DEFAULT_SCREENER_FILTERS } from "../../features/screener/screenerUrlState";
import ResultsTable from "./ResultsTable";

const mocks = vi.hoisted(() => ({ isNarrow: false }));

vi.mock("../../hooks/useMediaQuery", () => ({
  useMediaQuery: () => mocks.isNarrow,
}));

describe("ResultsTable", () => {
  it("exposes selected stock codes for batch actions", () => {
    mocks.isNarrow = false;
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
          strategySignalAges={new Map([["600519", 3]])}
          strategyReturnsSinceSignal={new Map([["600519", 7.14]])}
          strategyAverageAmounts={new Map([["600519", 12.5]])}
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
      "/stock/600519",
    );
    expect(screen.getByRole("link", { name: "600519" })).not.toHaveAttribute("target");
    expect(screen.getByText("主板")).toBeInTheDocument();
    expect(screen.getByText("制造业")).toBeInTheDocument();
    expect(screen.getByText("白酒Ⅱ")).not.toHaveClass("ant-tag");
    expect(screen.getAllByText("申万二级").length).toBeGreaterThan(0);
    expect(screen.getAllByText("交易所行业").length).toBeGreaterThan(0);
    expect(screen.getByText("2026-08-17")).toBeInTheDocument();
    expect(screen.getByText("3 根")).toBeInTheDocument();
    expect(screen.getByLabelText("上涨 7.14%")).toBeInTheDocument();
    expect(screen.getByText("12.50")).toBeInTheDocument();
    expect(screen.getAllByText("20日均成交额（亿）").length).toBeGreaterThan(0);
    expect(screen.getByText("eastmoney-direct-fallback")).toBeInTheDocument();
  });

  it("shows strategy signal metrics directly on narrow screens", () => {
    mocks.isNarrow = true;
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
          onSelectedCodesChange={vi.fn()}
          strategySignalDates={new Map([["600519", "2026-08-17"]])}
          strategySignalAges={new Map([["600519", 3]])}
          strategyReturnsSinceSignal={new Map([["600519", 7.14]])}
        />
      </MemoryRouter>,
    );

    expect(screen.getByRole("columnheader", { name: /信号年龄/ })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /信号收益/ })).toBeInTheDocument();
    expect(screen.getByText("3 根")).toBeInTheDocument();
    expect(screen.getByLabelText("上涨 7.14%")).toBeInTheDocument();
  });

  it("sorts strategy metrics locally without requesting server data", () => {
    mocks.isNarrow = false;
    const onPageChange = vi.fn();
    const onSortChange = vi.fn();
    render(
      <MemoryRouter>
        <ResultsTable
          data={{
            items: [
              {
                code: "600519",
                name: "贵州茅台",
                price: 1500,
                change_pct: 1,
                pe_ttm: 20,
                pb: 8,
                market_cap: 18000,
                turnover_pct: 0.5,
                volume: 1000,
                second_industry: null,
              },
              {
                code: "000001",
                name: "平安银行",
                price: 12,
                change_pct: -0.5,
                pe_ttm: 6,
                pb: 0.7,
                market_cap: 2300,
                turnover_pct: 0.8,
                volume: 2000,
                second_industry: null,
              },
            ],
            total: 2,
            page: 1,
            page_size: 50,
          }}
          isLoading={false}
          percentileMap={new Map()}
          showPercentile={false}
          onPageChange={onPageChange}
          filters={DEFAULT_SCREENER_FILTERS}
          onSortChange={onSortChange}
          selectedCodes={[]}
          onSelectedCodesChange={vi.fn()}
          strategySignalDates={new Map([
            ["600519", "2026-08-17"],
            ["000001", "2026-08-18"],
          ])}
          strategySignalAges={new Map([
            ["600519", 3],
            ["000001", 1],
          ])}
          strategyReturnsSinceSignal={new Map([
            ["600519", 7.14],
            ["000001", 2],
          ])}
          strategyAverageAmounts={new Map([
            ["600519", 12.5],
            ["000001", 8],
          ])}
        />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("columnheader", { name: /信号年龄/ }));

    const stockCodes = screen.getAllByRole("link").map((link) => link.textContent);
    expect(stockCodes).toEqual(["000001", "600519"]);
    expect(onSortChange).not.toHaveBeenCalled();
    expect(onPageChange).not.toHaveBeenCalled();
  });

  it("restores server sorting after strategy results are cleared", async () => {
    mocks.isNarrow = false;
    const props = {
      data: {
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
          second_industry: null,
        }],
        total: 1,
        page: 1,
        page_size: 50,
      },
      isLoading: false,
      percentileMap: new Map<string, number | null>(),
      showPercentile: false,
      onPageChange: vi.fn(),
      filters: DEFAULT_SCREENER_FILTERS,
      onSortChange: vi.fn(),
      selectedCodes: [] as string[],
      onSelectedCodesChange: vi.fn(),
    };
    const { rerender } = render(
      <MemoryRouter>
        <ResultsTable
          {...props}
          strategySignalDates={new Map([["600519", "2026-08-17"]])}
          strategySignalAges={new Map([["600519", 3]])}
        />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("columnheader", { name: /信号年龄/ }));
    rerender(
      <MemoryRouter>
        <ResultsTable {...props} />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole("columnheader", { name: /市值\(亿\)/ })).toHaveAttribute(
        "aria-sort",
        "descending",
      );
    });
  });

  it("renders amplitude column, broken-net badge, and supports amplitude sorting", () => {
    mocks.isNarrow = false;
    const onSortChange = vi.fn();
    render(
      <MemoryRouter>
        <ResultsTable
          data={{
            items: [{
              code: "601398",
              name: "工商银行",
              price: 5.8,
              change_pct: 0.5,
              pe_ttm: 5.2,
              pb: 0.58,
              is_broken_net: true,
              amplitude: 1.85,
              market_cap: 20000,
              turnover_pct: 0.12,
              volume: 500000,
              second_industry: null,
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
          onSortChange={onSortChange}
          selectedCodes={[]}
          onSelectedCodesChange={vi.fn()}
        />
      </MemoryRouter>,
    );

    expect(screen.getByText("破净")).toBeInTheDocument();
    expect(screen.getByText("1.85%")).toBeInTheDocument();

    const amplitudeHeader = screen.getByRole("columnheader", { name: /振幅/ });
    fireEvent.click(amplitudeHeader);
    expect(onSortChange).toHaveBeenCalledWith("amplitude", "asc");
  });
});
