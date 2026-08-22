import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import FundFlowTab from "./FundFlowTab";

const mocks = vi.hoisted(() => ({
  useHsgtFlow: vi.fn(() => ({
    data: {
      updated_at: "2026-08-13 10:30:00",
      unit: "亿元",
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
    return (
      <div
        data-testid="northbound-chart"
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
}));

describe("FundFlowTab", () => {
  it("keeps metric and chart identity colors aligned without dropping deep-connect points", () => {
    render(<FundFlowTab />);

    expect(screen.getByText("北向资金实时流向")).toBeInTheDocument();
    expect(screen.getByText("北向合计净买入")).toBeInTheDocument();
    expect(screen.getByText("+10.30")).toBeInTheDocument();

    const chart = screen.getByTestId("northbound-chart");
    expect(chart).toHaveAttribute("data-contain-label", "true");
    expect(chart).toHaveAttribute("data-legend", "北向合计,沪股通,深股通");
    expect(chart).toHaveAttribute("data-line-colors", "#f79009,#f5222d,#52c41a");
    expect(chart).toHaveAttribute("data-item-colors", "#f79009,#f5222d,#52c41a");
    expect(chart).toHaveAttribute("data-series-lengths", "3,3,3");
    expect(screen.getByText(/数据源：同花顺 data\.hexin\.cn 原始接口/)).toHaveTextContent("沪股通 3/3 点，深股通 3/3 点");

    expect(screen.getByTestId("northbound-total").querySelector(".ant-statistic-content")).toHaveStyle({ color: "#f79009" });
    expect(screen.getByTestId("northbound-shanghai").querySelector(".ant-statistic-content")).toHaveStyle({ color: "#f5222d" });
    expect(screen.getByTestId("northbound-shenzhen").querySelector(".ant-statistic-content")).toHaveStyle({ color: "#52c41a" });
    expect(mocks.useHsgtFlow).toHaveBeenCalledWith();
  });
});
