import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { PortfolioEquityCurveResponse } from "../../types/portfolio";
import PortfolioEquityCurve from "./PortfolioEquityCurve";
import { buildPortfolioEquityOption } from "./portfolioEquityChartOptions";

const mocks = vi.hoisted(() => ({ usePortfolioEquityCurve: vi.fn(), refetch: vi.fn() }));

vi.mock("../../api/queries", () => ({
  usePortfolioEquityCurve: mocks.usePortfolioEquityCurve,
}));
vi.mock("../../hooks/useMediaQuery", () => ({ useMediaQuery: () => false }));
vi.mock("echarts-for-react/lib/core", () => ({
  default: ({ option }: { option: unknown }) => (
    <div data-testid="portfolio-equity-chart" data-option={JSON.stringify(option)} />
  ),
}));

const totalCurve: PortfolioEquityCurveResponse = {
  mode: "total_assets",
  start_date: "2026-01-02",
  end_date: "2026-01-05",
  initial_cash: 10000,
  current_total_assets: 10193,
  current_securities_value: 720,
  total_return_pct: 1.93,
  max_drawdown_pct: -1.98,
  points: [
    { date: "2026-01-02", cash_balance: 8995, securities_value: 1000, total_assets: 9995, cumulative_return_pct: -0.05, drawdown_pct: -0.05, unpriced_count: 0 },
    { date: "2026-01-05", cash_balance: 9473, securities_value: 720, total_assets: 10193, cumulative_return_pct: 1.93, drawdown_pct: 0, unpriced_count: 0 },
  ],
  sources: ["market_daily:confirmed"],
  warnings: ["曲线按不复权收盘价估值。"],
};

const colors = {
  primary: "#1677ff", up: "#ef4444", textMuted: "#64748b",
  textSecondary: "#334155", border: "#e2e8f0",
} as Parameters<typeof buildPortfolioEquityOption>[1];

describe("PortfolioEquityCurve", () => {
  it("renders total assets, cash and securities series with summary metrics", () => {
    mocks.usePortfolioEquityCurve.mockReturnValue({
      data: totalCurve,
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: mocks.refetch,
    });

    render(<PortfolioEquityCurve />);

    expect(screen.getByText("总资产变化曲线")).toBeInTheDocument();
    expect(screen.getByText("总资产口径")).toBeInTheDocument();
    expect(screen.getByText("期末总资产").closest(".ant-statistic")).toHaveTextContent("10,193.00");
    expect(screen.getByText("累计收益率").closest(".ant-statistic")).toHaveTextContent("1.93%");
    expect(screen.getByText("最大回撤").closest(".ant-statistic")).toHaveTextContent("-1.98%");
    const option = JSON.parse(screen.getByTestId("portfolio-equity-chart").getAttribute("data-option") || "{}");
    expect(option.series.map((item: { name: string }) => item.name)).toEqual(["总资产", "证券市值", "现金余额"]);
    fireEvent.click(screen.getByRole("button", { name: /刷新/ }));
    expect(mocks.refetch).toHaveBeenCalledTimes(1);
  });

  it("uses securities-only series without return metrics when initial cash is missing", () => {
    const curve: PortfolioEquityCurveResponse = {
      ...totalCurve,
      mode: "securities_only",
      initial_cash: null,
      current_total_assets: null,
      current_securities_value: 1200,
      total_return_pct: null,
      max_drawdown_pct: null,
      points: (totalCurve.points ?? []).map((point) => ({ ...point, cash_balance: null, total_assets: null, cumulative_return_pct: null, drawdown_pct: null })),
    };
    mocks.usePortfolioEquityCurve.mockReturnValue({
      data: curve, isLoading: false, isFetching: false, error: null, refetch: mocks.refetch,
    });

    render(<PortfolioEquityCurve />);

    expect(screen.getByText("仅证券市值")).toBeInTheDocument();
    expect(screen.getByText("期末证券市值").closest(".ant-statistic")).toHaveTextContent("1,200.00");
    expect(screen.queryByText("累计收益率")).not.toBeInTheDocument();
    const option = buildPortfolioEquityOption(curve, colors, false);
    expect(option.series.map((item) => item.name)).toEqual(["证券市值"]);
  });
});
