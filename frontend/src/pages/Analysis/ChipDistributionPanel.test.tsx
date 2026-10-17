import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ChipDistribution } from "../../types/stock";
import ChipDistributionPanel from "../../features/stock-insights/ChipDistributionPanel";

const chartOptions: unknown[] = [];

vi.mock("echarts-for-react/lib/core", () => ({
  default: ({ option }: { option: unknown }) => {
    chartOptions.push(option);
    return <div data-testid="chip-echarts" />;
  },
}));

vi.mock("../../theme/hooks", () => ({
  useColors: () => ({
    primary: "#1677ff",
    border: "#333",
    textPrimary: "#fff",
    textSecondary: "#aaa",
    up: "#f00",
  }),
  useStyles: () => ({ cardStyle: {} }),
}));

const data: ChipDistribution = {
  code: "600519",
  as_of_date: "2026-08-31",
  source: "local",
  price: 105,
  profit_ratio: 0.6823,
  avg_cost: 99.5,
  cost_90: { low: 88, high: 112 },
  cost_70: { low: 94, high: 106 },
  concentration_90: 0.12,
  concentration_70: 0.06,
  peak_price: 98.8,
  histogram: [
    { price: 100, ratio: 0.4 },
    { price: 99, ratio: 0.35 },
    { price: 106, ratio: 0.25 },
  ],
};

describe("ChipDistributionPanel", () => {
  it("renders local chip metrics, cost ranges, and a sorted horizontal histogram", () => {
    chartOptions.length = 0;
    render(<ChipDistributionPanel data={data} />);

    expect(screen.getByText("筹码分布（本地估算）")).toBeInTheDocument();
    expect(screen.getByText("68.23%")).toBeInTheDocument();
    expect(screen.getByText("98.80")).toBeInTheDocument();
    expect(screen.getByText("94.00 – 106.00")).toBeInTheDocument();
    expect(screen.getByText("88.00 – 112.00")).toBeInTheDocument();
    expect(screen.getByText(/截至 2026-08-31/)).toBeInTheDocument();
    expect(screen.getByTestId("chip-distribution-chart")).toBeInTheDocument();

    const option = chartOptions[chartOptions.length - 1] as {
      yAxis: { data: string[] };
      series: Array<{ data: Array<{ value: number; itemStyle: { color: string } }> }>;
    };
    expect(option.yAxis.data).toEqual(["99.00", "100.00", "106.00"]);
    expect(option.series[0].data.map((item) => item.value)).toEqual([0.35, 0.4, 0.25]);
    expect(option.series[0].data.map((item) => item.itemStyle.color)).toEqual(["#f00", "#f00", "#1677ff"]);
  });
});
