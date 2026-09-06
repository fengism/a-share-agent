import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AnalysisPageData, KlineData } from "../../types/stock";
import AnalysisChartsSection from "./AnalysisChartsSection";

const mocks = vi.hoisted(() => ({
  useKlineData: vi.fn(),
  useStockIntraday: vi.fn(),
}));

vi.mock("../../api/queries", () => ({
  useKlineData: mocks.useKlineData,
  useStockIntraday: mocks.useStockIntraday,
}));

vi.mock("../../charts/LazyKlineChart", () => ({
  default: ({ data, viewKey }: { data: Array<{ close: number }>; viewKey: string }) => (
    <div data-testid="kline-chart" data-view-key={viewKey}>{data[0]?.close}</div>
  ),
}));
vi.mock("../../charts/IntradayChart", () => ({ default: () => null }));
vi.mock("../../charts/IndicatorSubCharts", () => ({
  default: ({ types }: { types?: string[] }) => (
    <div data-testid="analysis-indicators">{types?.join(",") ?? "all"}</div>
  ),
}));
vi.mock("./ChipDistributionPanel", () => ({
  default: ({ data }: { data: { peak_price: number } }) => (
    <div data-testid="chip-distribution-panel">{data.peak_price}</div>
  ),
}));
vi.mock("../../theme/hooks", () => ({
  useColors: () => ({
    primary: "#1677ff",
    border: "#333",
    nestedBg: "#111",
    elevatedBg: "#222",
    hoverBg: "#222",
    textPrimary: "#fff",
    textSecondary: "#aaa",
    up: "#f00",
    down: "#0f0",
  }),
  useStyles: () => ({ cardStyle: {} }),
}));

const defaultKline = {
  code: "600519",
  period: "daily",
  items: [{ date: "2026-08-01", open: 1, close: 10, high: 11, low: 1, volume: 1 }],
} as KlineData;
const weeklyKline = {
  code: "600519",
  period: "weekly",
  items: [{ date: "2026-08-01", open: 1, close: 20, high: 21, low: 1, volume: 1 }],
} as KlineData;

describe("AnalysisChartsSection", () => {
  beforeEach(() => {
    mocks.useKlineData.mockReset();
    mocks.useStockIntraday.mockReset().mockImplementation((_code, initialData) => ({
      data: initialData ?? undefined,
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    }));
    mocks.useKlineData.mockImplementation((_code, period, adjust, enabled) => ({
      data: enabled && period === "weekly" && adjust === "qfq" ? weeklyKline : undefined,
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    }));
  });

  it("reuses aggregate data by default and fetches the selected non-default K-line", () => {
    render(
      <AnalysisChartsSection
        code="600519"
        pageData={{ kline: defaultKline } as AnalysisPageData}
      />,
    );

    expect(mocks.useKlineData).toHaveBeenLastCalledWith("600519", "daily", "qfq", false);
    expect(screen.getByTestId("kline-chart")).toHaveTextContent("10");

    fireEvent.click(screen.getByText("周K"));

    expect(mocks.useKlineData).toHaveBeenLastCalledWith("600519", "weekly", "qfq", true);
    expect(screen.getByTestId("kline-chart")).toHaveTextContent("20");
  });


  it("leaves MACD on the stock profile while retaining RSI and KDJ", () => {
    render(
      <AnalysisChartsSection
        code="600519"
        pageData={{ kline: defaultKline } as AnalysisPageData}
      />,
    );

    expect(screen.getByTestId("analysis-indicators")).toHaveTextContent("rsi,kdj");
    expect(screen.getByTestId("analysis-indicators")).not.toHaveTextContent("macd");
  });

  it("leaves chip distribution to the stock profile page", () => {
    render(
      <AnalysisChartsSection
        code="600519"
        pageData={{
          kline: defaultKline,
          chip_distribution: { peak_price: 98.8 },
        } as unknown as AnalysisPageData}
      />,
    );

    expect(screen.queryByText("筹码分布")).not.toBeInTheDocument();
    expect(screen.queryByTestId("chip-distribution-panel")).not.toBeInTheDocument();
  });

  it("shows a local retry action when the selected K-line request fails", () => {
    const refetch = vi.fn();
    mocks.useKlineData.mockImplementation((_code, _period, _adjust, enabled) => ({
      data: undefined,
      isLoading: false,
      isFetching: false,
      error: enabled ? new Error("provider unavailable") : null,
      refetch,
    }));

    render(
      <AnalysisChartsSection
        code="600519"
        pageData={{ kline: defaultKline } as AnalysisPageData}
      />,
    );
    fireEvent.click(screen.getByText("周K"));
    fireEvent.click(screen.getByRole("button", { name: /重\s*试/ }));

    expect(screen.getByText("K 线加载失败")).toBeInTheDocument();
    expect(refetch).toHaveBeenCalledOnce();
  });
});
