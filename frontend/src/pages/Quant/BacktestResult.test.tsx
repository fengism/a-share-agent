import { render, screen } from "@testing-library/react";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import type { ComponentProps } from "react";
import type { QuantBacktestResult } from "../../api/queries";
import BacktestResult from "./BacktestResult";

vi.mock("../../hooks/useMediaQuery", () => ({ useMediaQuery: () => true }));
vi.mock("echarts-for-react/lib/core", () => ({
  default: (props: ComponentProps<"div"> & { "data-testid"?: string }) => (
    <div data-testid={props["data-testid"]} style={props.style} />
  ),
}));

const nativeGetComputedStyle = window.getComputedStyle.bind(window);

beforeAll(() => {
  vi.spyOn(window, "getComputedStyle").mockImplementation((element) => nativeGetComputedStyle(element));
});

afterAll(() => {
  vi.restoreAllMocks();
});

function makeResult(overrides: Partial<QuantBacktestResult> = {}): QuantBacktestResult {
  return {
    engine_version: "v1",
    data_hash: "hash",
    data_sources: ["akshare"],
    codes: ["600519"],
    metrics: {
      total_return: 12.34,
      annualized_return: 11.2,
      annualized_volatility: 10,
      benchmark_return: 8,
      excess_return: 4.34,
      max_drawdown: -5.2,
      profit_loss_ratio: 1.8,
      sharpe_ratio: 1.1,
      turnover_rate: 100,
      trade_count: 1,
      win_rate: 60,
    },
    equity_curve: [{ date: "2026-01-01", equity: 1.12, benchmark: 1.08, drawdown: -0.03 }],
    monthly_returns: [{ month: "2026-01", return_pct: 2.5 }],
    trades: [{
      date: "2026-01-02",
      code: "600519",
      side: "buy",
      price: 1500,
      shares: 100,
      amount: 150_000,
      fee: 45,
      realized_pnl: null,
    }],
    ...overrides,
  };
}

describe("BacktestResult", () => {
  it("renders metrics, compact charts and result tables", () => {
    render(<BacktestResult result={makeResult()} />);

    expect(screen.getByRole("region", { name: "回测结果" })).toBeInTheDocument();
    expect(screen.getByText("总收益")).toBeInTheDocument();
    expect(screen.getByText("总收益").closest(".ant-statistic")).toHaveTextContent("12.34%");
    expect(screen.getByText("基准收益")).toBeInTheDocument();
    expect(screen.getByText("1 次")).toBeInTheDocument();
    expect(screen.getByText("akshare")).toBeInTheDocument();
    expect(screen.getByText("v1")).toBeInTheDocument();
    expect(screen.getByTestId("equity-chart")).toHaveStyle({ height: "260px" });
    expect(screen.getByTestId("drawdown-chart")).toHaveStyle({ height: "260px" });
    expect(screen.getByText("2026-01")).toBeInTheDocument();
    expect(screen.getByText("买入")).toBeInTheDocument();
  });

  it("shows clear empty states for charts and detail tables", () => {
    render(<BacktestResult result={makeResult({ equity_curve: [], monthly_returns: [], trades: [] })} />);

    expect(screen.getByText("暂无净值数据")).toBeInTheDocument();
    expect(screen.getByText("暂无回撤数据")).toBeInTheDocument();
    expect(screen.getByText("暂无月度收益")).toBeInTheDocument();
    expect(screen.getByText("暂无成交记录")).toBeInTheDocument();
    expect(screen.queryByTestId("equity-chart")).not.toBeInTheDocument();
  });
});
