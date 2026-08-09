import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { QuantBacktestRun } from "../../api/queries";
import BacktestHistory from "./BacktestHistory";

function makeRun(overrides: Partial<QuantBacktestRun> = {}): QuantBacktestRun {
  return {
    id: "run-one",
    name: "消费双均线",
    status: "succeeded",
    attempts: 1,
    created_at: 1_786_000_000,
    updated_at: 1_786_000_010,
    completed_at: 1_786_000_010,
    request: {
      name: "消费双均线",
      universe: { source: "custom", codes: ["600519"] },
      strategy: {
        type: "ma_cross",
        fast_period: 5,
        slow_period: 20,
        lookback_period: 20,
        rsi_period: 14,
        buy_threshold: 30,
        sell_threshold: 70,
      },
      start_date: "2025-01-01",
      end_date: "2026-01-01",
      benchmark: "000300",
    },
    ...overrides,
  };
}

const baseProps = {
  selectedRunId: undefined,
  isLoading: false,
  isFetching: false,
  error: undefined,
  onRefresh: vi.fn(),
  onSelect: vi.fn(),
  onRetryRun: vi.fn(),
  onDeleteRun: vi.fn(),
};

describe("BacktestHistory", () => {
  it("renders reusable loading, error and empty states", () => {
    const { rerender } = render(<BacktestHistory {...baseProps} runs={[]} isLoading />);
    expect(screen.getByLabelText("数据加载中")).toBeInTheDocument();

    rerender(<BacktestHistory {...baseProps} runs={[]} error={new Error("history unavailable")} />);
    expect(screen.getByText("history unavailable")).toBeInTheDocument();

    rerender(<BacktestHistory {...baseProps} runs={[]} />);
    expect(screen.getByText("暂无回测记录，先创建一次策略回测")).toBeInTheDocument();
  });

  it("selects, retries and deletes history runs", async () => {
    const onSelect = vi.fn();
    const onRetryRun = vi.fn();
    const onDeleteRun = vi.fn();
    const failedRun = makeRun({ id: "run-failed", name: "失败策略", status: "failed", error: "provider error" });
    render(
      <BacktestHistory
        {...baseProps}
        runs={[makeRun(), failedRun]}
        selectedRunId="run-one"
        onSelect={onSelect}
        onRetryRun={onRetryRun}
        onDeleteRun={onDeleteRun}
      />,
    );

    expect(screen.getByRole("button", { name: "查看回测 消费双均线" })).toHaveAttribute("aria-current", "true");
    fireEvent.click(screen.getByRole("button", { name: "查看回测 失败策略" }));
    fireEvent.click(screen.getByRole("button", { name: "重试" }));
    expect(onSelect).toHaveBeenCalledWith("run-failed");
    expect(onRetryRun).toHaveBeenCalledWith("run-failed");

    fireEvent.click(screen.getByRole("button", { name: "删除回测 消费双均线" }));
    fireEvent.click(await screen.findByRole("button", { name: /^删\s*除$/ }));
    await waitFor(() => expect(onDeleteRun).toHaveBeenCalledWith("run-one"));
  });

  it("filters runs by keyword and status without changing the source list", async () => {
    const failedRun = makeRun({ id: "run-failed", name: "银行突破", status: "failed" });
    render(<BacktestHistory {...baseProps} runs={[makeRun(), failedRun]} />);

    fireEvent.change(screen.getByRole("textbox", { name: "搜索历史回测" }), { target: { value: "银行" } });
    expect(screen.getByRole("button", { name: "查看回测 银行突破" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "查看回测 消费双均线" })).not.toBeInTheDocument();
    expect(screen.getByText("1/2 条")).toBeInTheDocument();

    fireEvent.change(screen.getByRole("textbox", { name: "搜索历史回测" }), { target: { value: "" } });
    fireEvent.mouseDown(screen.getByRole("combobox", { name: "历史状态" }));
    fireEvent.click(await screen.findByTitle("失败"));

    expect(screen.getByRole("button", { name: "查看回测 银行突破" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "查看回测 消费双均线" })).not.toBeInTheDocument();
  });
});
