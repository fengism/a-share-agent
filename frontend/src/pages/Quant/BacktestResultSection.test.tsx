import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import BacktestResultSection from "./BacktestResultSection";

vi.mock("./quantLazyLoaders", () => ({
  loadBacktestResult: () => Promise.resolve({ default: () => <div>已加载独立结果视图</div> }),
}));

const run = {
  id: "run-one",
  name: "测试回测",
  status: "succeeded" as const,
  attempts: 1,
  created_at: 1,
  updated_at: 2,
  completed_at: 2,
  request: {
    name: "测试回测",
    universe: { source: "custom" as const, codes: ["600519"] },
    strategy: { type: "ma_cross" as const, version: "1.0.0", parameters: {} },
    start_date: "2025-01-01",
    end_date: "2026-01-01",
    benchmark: "000300",
  },
  result: {
    engine_version: "v1",
    data_hash: "hash",
    data_sources: ["tencent"],
    codes: ["600519"],
    metrics: {
      total_return: 1,
      annualized_return: 1,
      annualized_volatility: 1,
      max_drawdown: -1,
      turnover_rate: 1,
      trade_count: 1,
    },
    equity_curve: [],
    monthly_returns: [],
    trades: [],
  },
};

describe("BacktestResultSection", () => {
  it("shows an empty state without a selected completed run", () => {
    render(<BacktestResultSection />);

    expect(screen.getByRole("region", { name: "回测结果分析" })).toBeInTheDocument();
    expect(screen.getByText("请先创建或选择一个回测任务")).toBeInTheDocument();
  });

  it("loads the result only inside the result view", async () => {
    const onBackToRuns = vi.fn();
    render(<BacktestResultSection run={run} onBackToRuns={onBackToRuns} />);

    expect(screen.getByText("测试回测")).toBeInTheDocument();
    expect(screen.getByText(/600519.*2025-01-01 至 2026-01-01/)).toBeInTheDocument();
    expect(await screen.findByText("已加载独立结果视图")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /返回任务记录/ }));
    expect(onBackToRuns).toHaveBeenCalledTimes(1);
  });
});
