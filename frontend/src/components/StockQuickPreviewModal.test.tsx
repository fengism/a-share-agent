import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { BrowserRouter } from "react-router-dom";
import StockQuickPreviewModal from "./StockQuickPreviewModal";

vi.mock("../api/queryHooks/stock", () => ({
  useStockInfo: (code: string) => ({
    data: code === "600519" ? {
      code: "600519",
      name: "贵州茅台",
      current_price: 1850.5,
      previous_close: 1810.0,
      first_industry: { code: "1", name: "白酒" },
      turnover_pct: 1.25,
    } : null,
    isLoading: false,
  }),
  useKlineData: () => ({
    data: {
      code: "600519",
      period: "daily",
      adjust: "qfq",
      items: [
        {
          date: "2026-10-29",
          open: 1835,
          high: 1860,
          low: 1835,
          close: 1850.5,
          volume: 10000,
          amount: 18505000,
          change_pct: 2.15,
          turnover_pct: 1.25,
        },
      ],
    },
    isLoading: false,
  }),
  useStockIntraday: () => ({
    data: {
      code: "600519",
      items: [
        { time: "2026-10-29 09:30:00", price: 1840, volume: 500, amount: 920000, avg_price: 1840 },
        { time: "2026-10-29 09:31:00", price: 1850.5, volume: 600, amount: 1110300, avg_price: 1845 },
      ],
    },
    isLoading: false,
  }),
}));

vi.mock("../api/queryHooks/watchlist", () => ({
  useWatchlist: () => ({ data: { items: [], total: 0 } }),
  useAddWatchlistItem: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock("../charts/LazyKlineChart", () => ({
  default: () => <div data-testid="lazy-kline-chart">LazyKlineChart Mock</div>,
}));

vi.mock("../charts/IntradayChart", () => ({
  default: () => <div data-testid="intraday-chart">IntradayChart Mock</div>,
}));

describe("StockQuickPreviewModal", () => {
  it("renders stock info, stats and kline chart", () => {
    render(
      <BrowserRouter>
        <StockQuickPreviewModal
          open={true}
          code="600519"
          name="贵州茅台"
          onClose={vi.fn()}
        />
      </BrowserRouter>,
    );

    expect(screen.getByText("贵州茅台")).toBeInTheDocument();
    expect(screen.getByText("600519")).toBeInTheDocument();
    expect(screen.getByText("白酒")).toBeInTheDocument();
    expect(screen.getByText("1850.50")).toBeInTheDocument();
    expect(screen.getByTestId("lazy-kline-chart")).toBeInTheDocument();
    expect(screen.getByText("深度研报")).toBeInTheDocument();
  });

  it("supports switching between kline and intraday charts", () => {
    render(
      <BrowserRouter>
        <StockQuickPreviewModal
          open={true}
          code="600519"
          name="贵州茅台"
          onClose={vi.fn()}
        />
      </BrowserRouter>,
    );

    expect(screen.getByTestId("lazy-kline-chart")).toBeInTheDocument();
    expect(screen.queryByTestId("intraday-chart")).not.toBeInTheDocument();

    const intradayTab = screen.getByText("当日分时");
    fireEvent.click(intradayTab);

    expect(screen.getByTestId("intraday-chart")).toBeInTheDocument();
    expect(screen.queryByTestId("lazy-kline-chart")).not.toBeInTheDocument();
  });
});
