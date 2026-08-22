import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import BacktestTaskWorkspace from "./BacktestTaskWorkspace";
import type { QuantRunController } from "./useQuantRunController";

const completedRun = {
  id: "run-one",
  name: "已完成回测",
  status: "succeeded" as const,
  attempts: 1,
  created_at: 1,
  updated_at: 2,
  completed_at: 2,
  request: {
    name: "已完成回测",
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

function controller(): QuantRunController {
  return {
    runs: [completedRun],
    selectedRun: completedRun,
    selectedRunId: completedRun.id,
    isRunActionPending: false,
    isHistoryLoading: false,
    isHistoryFetching: false,
    runHistoryError: undefined,
    retryingRunId: undefined,
    deletingRunId: undefined,
    selectRun: vi.fn(),
    cancelRun: vi.fn(),
    retryRun: vi.fn(),
    deleteRun: vi.fn(),
    refreshRuns: vi.fn(),
  } as unknown as QuantRunController;
}

describe("BacktestTaskWorkspace", () => {
  it("offers direct setup and current-result actions", () => {
    const onOpenSetup = vi.fn();
    const onOpenResult = vi.fn();
    render(
      <BacktestTaskWorkspace
        controller={controller()}
        onOpenSetup={onOpenSetup}
        onOpenResult={onOpenResult}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /新建回测/ }));
    fireEvent.click(screen.getByRole("button", { name: /查看当前结果/ }));

    expect(onOpenSetup).toHaveBeenCalledTimes(1);
    expect(onOpenResult).toHaveBeenCalledWith("run-one");
  });
});
