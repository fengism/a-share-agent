import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { BrowserRouter } from "react-router-dom";
import StockWorkspaceDrawer from "./StockWorkspaceDrawer";

const dragonTigerRows = [
  {
    side: "buy" as const,
    code: "600519",
    operate_name: "机构专用",
    buy_amount: 120000000,
    sell_amount: 0,
    net_amount: 120000000,
    buy_ratio: 0.12,
    sell_ratio: 0,
  },
];

vi.mock("../api/queries", () => ({
  useStockInfo: (code: string) => ({
    data: code === "600519" ? {
      code: "600519",
      name: "贵州茅台",
      current_price: 1850.5,
      previous_close: 1810.0,
      first_industry: { code: "1", name: "白酒" },
      turnover_pct: 1.25,
      market_cap: 2325000000000,
      float_market_cap: 1800000000000,
      pe_ttm: 28.4,
      pe_static: 30.1,
      pb: 8.2,
      total_shares: 1256197800,
      circulating_shares: 1256197800,
      listing_date: "2001-08-27",
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
  useStockChipDistribution: () => ({
    data: {
      code: "600519",
      as_of_date: "2026-10-29",
      source: "test",
      price: 1850.5,
      profit_ratio: 0.82,
      avg_cost: 1750,
      cost_90: { low: 1500, high: 2000 },
      cost_70: { low: 1600, high: 1900 },
      concentration_90: 0.12,
      concentration_70: 0.08,
      peak_price: 1800,
      histogram: [{ price: 1800, ratio: 0.3 }],
    },
    isLoading: false,
  }),
  useDragonTigerDetail: (_code: string, reportDate: string) => ({
    data: reportDate ? dragonTigerRows : [],
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

vi.mock("../features/stock-insights/ChipDistributionPanel", () => ({
  default: () => <div data-testid="chip-distribution-panel">ChipDistributionPanel Mock</div>,
}));

vi.mock("../features/stock-insights/FundFlowPanel", () => ({
  default: ({ code }: { code: string }) => <div data-testid="fund-flow-panel">FundFlowPanel {code}</div>,
}));

function renderDrawer() {
  return render(
    <BrowserRouter>
      <StockWorkspaceDrawer open={true} code="600519" name="贵州茅台" onClose={vi.fn()} />
    </BrowserRouter>,
  );
}

describe("StockWorkspaceDrawer", () => {
  it("renders stock info, stats and kline chart", () => {
    renderDrawer();

    expect(screen.getByText("贵州茅台")).toBeInTheDocument();
    expect(screen.getByText("600519")).toBeInTheDocument();
    expect(screen.getByText("白酒")).toBeInTheDocument();
    expect(screen.getByText("1850.50")).toBeInTheDocument();
    expect(screen.getByTestId("lazy-kline-chart")).toBeInTheDocument();
    expect(screen.getAllByText("深度研报").length).toBeGreaterThan(0);
  });

  it("exposes the four workspace tabs", () => {
    renderDrawer();

    expect(screen.getByRole("tab", { name: "K线走势" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "核心指标" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "主力与龙虎榜" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "AI 诊断" })).toBeInTheDocument();
  });

  it("supports switching between kline, intraday and chip views", () => {
    renderDrawer();

    expect(screen.getByTestId("lazy-kline-chart")).toBeInTheDocument();
    expect(screen.queryByTestId("intraday-chart")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("当日分时"));
    expect(screen.getByTestId("intraday-chart")).toBeInTheDocument();
    expect(screen.queryByTestId("lazy-kline-chart")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("筹码分布"));
    expect(screen.getByTestId("chip-distribution-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("intraday-chart")).not.toBeInTheDocument();
  });

  it("shows key metrics from stock info", () => {
    renderDrawer();
    fireEvent.click(screen.getByRole("tab", { name: "核心指标" }));

    expect(screen.getByText("总市值")).toBeInTheDocument();
    expect(screen.getByText("2.33 万亿")).toBeInTheDocument();
    expect(screen.getByText("流通市值")).toBeInTheDocument();
    expect(screen.getByText("1.80 万亿")).toBeInTheDocument();
    expect(screen.getByText("市盈率 TTM")).toBeInTheDocument();
    expect(screen.getByText("28.40")).toBeInTheDocument();
    expect(screen.getByText("市净率")).toBeInTheDocument();
    expect(screen.getByText("2001-08-27")).toBeInTheDocument();
  });

  it("shows fund flow and dragon tiger seats", () => {
    renderDrawer();
    fireEvent.click(screen.getByRole("tab", { name: "主力与龙虎榜" }));

    expect(screen.getByTestId("fund-flow-panel")).toBeInTheDocument();
    expect(screen.getByText("龙虎榜机构席位")).toBeInTheDocument();
    expect(screen.getByText("机构专用")).toBeInTheDocument();
    expect(screen.getByText("买入")).toBeInTheDocument();
  });

  it("offers AI diagnosis shortcuts", () => {
    renderDrawer();
    fireEvent.click(screen.getByRole("tab", { name: "AI 诊断" }));

    expect(screen.getByText("AI 风险与看点诊断")).toBeInTheDocument();
    expect(screen.getByText("AI 同业对比")).toBeInTheDocument();
  });
});
