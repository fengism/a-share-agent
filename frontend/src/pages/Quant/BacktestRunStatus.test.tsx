import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { QuantBacktestRun } from "../../api/queries";
import BacktestRunStatus from "./BacktestRunStatus";

function makeRun(status: QuantBacktestRun["status"]): QuantBacktestRun {
  return {
    id: "run-one",
    name: "量化测试",
    status,
    attempts: 1,
    created_at: 1,
    updated_at: 1,
    request: {
      name: "量化测试",
      universe: { source: "custom", codes: ["600519"] },
      strategy: {
        type: "ma_cross",
        version: "1.0.0",
        name: "双均线趋势",
        parameters: { fast_period: 5, slow_period: 20 },
      },
      start_date: "2025-01-01",
      end_date: "2026-01-01",
      benchmark: "000300",
    },
  };
}

describe("BacktestRunStatus", () => {
  it("allows cancelling an active run", () => {
    const onCancel = vi.fn();
    render(<BacktestRunStatus run={makeRun("running")} onCancel={onCancel} onRetry={vi.fn()} />);

    expect(screen.getByText("正在加载行情并计算回测")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "取消回测" }));
    expect(onCancel).toHaveBeenCalledWith("run-one");
  });

  it("shows the failure reason and retry action", () => {
    const onRetry = vi.fn();
    render(
      <BacktestRunStatus
        run={{ ...makeRun("failed"), error: "行情源不可用" }}
        onCancel={vi.fn()}
        onRetry={onRetry}
      />,
    );

    expect(screen.getByText("行情源不可用")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "重试回测" }));
    expect(onRetry).toHaveBeenCalledWith("run-one");
  });
});
