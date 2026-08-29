import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import FundFlowPanel from "./FundFlowPanel";

const baseFundFlow = Array.from({ length: 75 }, (_, index) => ({
  date: new Date(Date.UTC(2026, 0, index + 1)).toISOString().slice(0, 10),
  main_net: index,
  super_net: index,
  large_net: index,
  mid_net: -index,
  small_net: -index,
  source: "test",
  source_api: "test",
  is_stale: index === 0,
}));
const fundFlow = [
  ...baseFundFlow.filter((_, index) => index % 2 === 0),
  ...baseFundFlow.filter((_, index) => index % 2 === 1),
  { ...baseFundFlow[74], date: "20260316", main_net: 999 },
];

vi.mock("../../api/queries", () => ({
  useStockFundFlow: () => ({
    data: fundFlow,
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

vi.mock("echarts-for-react/lib/core", () => ({
  default: ({ option }: { option: { xAxis: { data: string[] } } }) => (
    <div data-testid="fund-flow-chart" data-point-count={option.xAxis.data.length} />
  ),
}));

describe("FundFlowPanel", () => {
  it("uses one defensively capped 60-day dataset for summary, chart, and table", () => {
    render(<FundFlowPanel code="600519" isExportingPdf />);

    expect(screen.getByTestId("fund-flow-chart")).toHaveAttribute("data-point-count", "60");
    expect(screen.getAllByRole("row")).toHaveLength(61);
    expect(screen.getAllByText("2026-03-16").length).toBeGreaterThan(0);
    expect(screen.queryByText("20260316")).not.toBeInTheDocument();
    expect(screen.getByText("2026-01-16")).toBeInTheDocument();
    expect(screen.queryByText("2026-01-15")).not.toBeInTheDocument();
    expect(screen.queryByText("2026-01-01")).not.toBeInTheDocument();
    expect(screen.queryByText("资金流上游暂不可用，当前展示最近一次成功缓存")).not.toBeInTheDocument();
  });
});
