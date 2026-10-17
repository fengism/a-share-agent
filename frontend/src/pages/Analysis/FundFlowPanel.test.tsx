import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FundFlowPanel from "../../features/stock-insights/FundFlowPanel";

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

const mocks = vi.hoisted(() => ({ query: vi.fn(), more: vi.fn(), refetch: vi.fn() }));
vi.mock("../../api/queries", () => ({ useStockFundFlowPages: () => mocks.query() }));
beforeEach(() => {
  mocks.more.mockReset();
  mocks.query.mockReturnValue({ data: { pages: [{ items: fundFlow, total: 60 }] }, isLoading: false, error: null, refetch: mocks.refetch });
});

vi.mock("echarts-for-react/lib/core", () => ({
  default: ({ option }: { option: { xAxis: { data: string[] } } }) => (
    <div data-testid="fund-flow-chart" data-point-count={option.xAxis.data.length} />
  ),
}));

describe("FundFlowPanel", () => {
  it.each([false, true])("labels TDX estimates even when stale=%s", (isStale) => {
    mocks.query.mockReturnValue({ data: { pages: [{ items: [{ ...baseFundFlow[74], source: "tdxhub_stock_fund_flow_estimate", is_stale: isStale }], total: 1 }] } });
    render(<FundFlowPanel code="600519" />);
    expect(screen.getByText("备选数据源：TDXHub 分笔估算")).toBeVisible();
    expect(screen.getByText(/非交易所官方资金流/)).toBeVisible();
    expect(screen.queryByText("资金流上游暂不可用，当前展示最近一次成功缓存") !== null).toBe(isStale);
  });

  it("keeps loaded data visible after a later batch fails and retries only on demand", () => {
    mocks.query.mockReturnValue({
      data: { pages: [{ items: baseFundFlow.slice(0, 20), total: 60 }] },
      hasNextPage: true, isFetchNextPageError: true, isFetching: false,
      error: new Error("资金流批次加载失败"), fetchNextPage: mocks.more, refetch: mocks.refetch,
    });
    render(<FundFlowPanel code="600519" />);
    expect(screen.getByText(/已加载 20 \/ 60 个交易日/)).toBeVisible();
    expect(screen.getByTestId("fund-flow-chart")).toHaveAttribute("data-point-count", "20");
    expect(screen.getByText("后续批次加载失败，已加载数据仍可查看")).toBeVisible();
    expect(mocks.more).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "重试加载更多" }));
    expect(mocks.more).toHaveBeenCalledOnce();
  });

  it("uses one defensively capped 60-day dataset for summary, chart, and table", () => {
    render(<FundFlowPanel code="600519" isExportingPdf />);

    expect(screen.queryByText("备选数据源：TDXHub 分笔估算")).not.toBeInTheDocument();
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
