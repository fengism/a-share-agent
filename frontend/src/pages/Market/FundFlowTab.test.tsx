import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FundFlowTab from "./FundFlowTab";

const mocks = vi.hoisted(() => ({
  useHsgtFlow: vi.fn(),
  useNorthboundHistory: vi.fn(() => ({
    data: {
      source: "乐咕乐股",
      updated_at: "2026-09-03T20:00:00+08:00",
      unit: "亿元",
      index_name: "沪深300",
      is_stale: false,
      items: [
        { date: "2026-09-02", north_money: 15, sh_connect: 10, sz_connect: 5, south_money: 3, hs300_close: 4547.96 },
        { date: "2026-09-03", north_money: 24.27, sh_connect: 11.18, sz_connect: 13.09, south_money: 5.49, hs300_close: 4552.58 },
      ],
    },
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  })),
}));

vi.mock("echarts-for-react/lib/core", () => ({
  default: ({
    option,
  }: {
    option: {
      grid?: { containLabel?: boolean };
      legend?: { data?: string[] };
      series?: Array<{
        data?: Array<number | null>;
        itemStyle?: { color?: string };
        lineStyle?: { color?: string };
      }>;
    };
  }) => {
    const series = option.series ?? [];
    const testId = option.legend?.data?.includes("沪深300") ? "northbound-history-chart" : "northbound-chart";
    return (
      <div
        data-testid={testId}
        data-contain-label={String(option.grid?.containLabel)}
        data-legend={option.legend?.data?.join(",")}
        data-line-colors={series.map((item) => item.lineStyle?.color).join(",")}
        data-item-colors={series.map((item) => item.itemStyle?.color).join(",")}
        data-series-lengths={series.map((item) => item.data?.length ?? 0).join(",")}
      />
    );
  },
}));

vi.mock("../../charts/echarts-setup", () => ({ default: {} }));

vi.mock("../../styles/ui", () => ({
  useColors: () => ({
    primary: "#1677ff",
    textSecondary: "#8c8c8c",
    up: "#f5222d",
    down: "#52c41a",
    warning: "#f79009",
  }),
}));

vi.mock("../../api/queries", () => ({
  useHsgtFlow: mocks.useHsgtFlow,
  useNorthboundHistory: mocks.useNorthboundHistory,
}));

describe("FundFlowTab", () => {
  beforeEach(() => {
    mocks.useHsgtFlow.mockReset().mockReturnValue({
      data: {
        date: "2026-08-13",
        updated_at: "2026-08-13 10:30:00",
        unit: "亿元",
        is_stale: false,
        points: [
          { time: "10:29", hgt: 6.2, sgt: 3.8, total: 10 },
          { time: "10:30", hgt: 6.5, sgt: 4, total: 10.5 },
          { time: "10:31", hgt: 6.1, sgt: 4.2, total: 10.3 },
        ],
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    });
  });

  it("keeps metric and chart identity colors aligned without dropping deep-connect points", () => {
    render(<FundFlowTab />);

    expect(screen.getByText("北向资金实时流向")).toBeInTheDocument();
    expect(screen.getByText("北向合计净流入（数据商口径）")).toBeInTheDocument();
    expect(screen.getByText("+10.30")).toBeInTheDocument();

    const chart = screen.getByTestId("northbound-chart");
    expect(chart).toHaveAttribute("data-contain-label", "true");
    expect(chart).toHaveAttribute("data-legend", "北向合计,沪股通,深股通");
    expect(chart).toHaveAttribute("data-line-colors", "#f79009,#f5222d,#52c41a");
    expect(chart).toHaveAttribute("data-item-colors", "#f79009,#f5222d,#52c41a");
    expect(chart).toHaveAttribute("data-series-lengths", "3,3,3");
    expect(screen.getByText(/沪股通 3\/3 点/)).toHaveTextContent("沪股通 3/3 点，深股通 3/3 点");

    expect(screen.getByTestId("northbound-total").querySelector(".ant-statistic-content")).toHaveStyle({ color: "#f79009" });
    expect(screen.getByTestId("northbound-shanghai").querySelector(".ant-statistic-content")).toHaveStyle({ color: "#f5222d" });
    expect(screen.getByTestId("northbound-shenzhen").querySelector(".ant-statistic-content")).toHaveStyle({ color: "#52c41a" });
    expect(screen.getByText("北向成交总额与沪深300走势")).toBeInTheDocument();
    const historyChart = screen.getByTestId("northbound-history-chart");
    expect(historyChart).toHaveAttribute("data-contain-label", "true");
    expect(historyChart).toHaveAttribute("data-legend", "北向成交总额,沪深300");
    expect(historyChart).toHaveAttribute("data-series-lengths", "2,2");
    expect(screen.getByText(/数据来源：乐咕乐股/)).toBeInTheDocument();

    expect(mocks.useHsgtFlow).toHaveBeenCalledWith();
    expect(mocks.useNorthboundHistory).toHaveBeenCalledWith(500);
  });

  it("identifies persisted northbound data as a recent trading-day fallback", () => {
    mocks.useHsgtFlow.mockReturnValue({
      data: {
        date: "2026-08-12",
        updated_at: "2026-08-12 15:00:00",
        unit: "亿元",
        is_stale: true,
        points: [
          { time: "14:59", hgt: 6.2, sgt: 3.8, total: 10 },
          { time: "15:00", hgt: 6.5, sgt: 4, total: 10.5 },
        ],
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<FundFlowTab />);

    expect(screen.getByText("最近交易日北向资金流向")).toBeInTheDocument();
    expect(screen.getByText(/数据日期：2026-08-12/)).toBeInTheDocument();
    expect(screen.getByText("当前展示最近一次本地数据。")).toBeInTheDocument();
  });
});
