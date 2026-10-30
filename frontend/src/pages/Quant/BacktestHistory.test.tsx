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
        version: "1.0.0",
        name: "双均线趋势",
        parameters: { fast_period: 5, slow_period: 20 },
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
  it("renders metrics from lightweight summaries without loading full results", () => {
    render(<BacktestHistory {...baseProps} runs={[makeRun({
      result: null,
      summary_metrics: {
        total_return: 12.34, annualized_return: 15, annualized_volatility: 10,
        max_drawdown: -5, trade_count: 8, turnover_rate: 100,
      },
    })]} />);
    expect(screen.getByText("收益: +12.3%")).toBeInTheDocument();
  });

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

    expect(screen.queryByRole("textbox", { name: "搜索历史回测" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /筛选历史回测/ }));
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

  it("shows the actual strategy even when an old run name says double moving average", () => {
    const run = makeRun({
      name: "双均线回测",
      request: {
        name: "双均线回测",
        universe: { source: "custom", codes: ["600519"] },
        strategy: {
          type: "bias_reversal",
          version: "1.0.0",
          name: "BIAS 乖离率反转",
          parameters: { period: 6, buy_threshold: -3, sell_threshold: 3 },
        },
        start_date: "2025-01-01",
        end_date: "2026-01-01",
        benchmark: "000300",
      },
    });

    render(<BacktestHistory {...baseProps} runs={[run]} />);

    expect(screen.getByText(/BIAS 乖离率反转/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "查看回测 双均线回测" })).toBeInTheDocument();
  });


  it("filters history by the persisted strategy type", async () => {
    const biasRun = makeRun({
      id: "run-bias",
      name: "BIAS 实验",
      request: {
        name: "BIAS 实验",
        universe: { source: "custom", codes: ["600519"] },
        strategy: {
          type: "bias_reversal",
          version: "1.0.0",
          name: "BIAS 乖离率反转",
          parameters: { period: 6, buy_threshold: -3, sell_threshold: 3 },
        },
        start_date: "2025-01-01",
        end_date: "2026-01-01",
        benchmark: "000300",
      },
    });
    render(<BacktestHistory {...baseProps} runs={[makeRun(), biasRun]} />);

    fireEvent.click(screen.getByRole("button", { name: /筛选历史回测/ }));
    fireEvent.mouseDown(screen.getByRole("combobox", { name: "历史策略" }));
    fireEvent.click(await screen.findByText("BIAS 乖离率反转"));

    expect(screen.getByRole("button", { name: "查看回测 BIAS 实验" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "查看回测 消费双均线" })).not.toBeInTheDocument();
    expect(screen.getByText("1/2 条")).toBeInTheDocument();
  });

  it("loads more history pages only when more runs exist", async () => {
    const onLoadMore = vi.fn();
    const { rerender } = render(
      <BacktestHistory
        {...baseProps}
        runs={[makeRun()]}
        hasMore
        isLoadingMore={false}
        onLoadMore={onLoadMore}
      />,
    );

    const button = screen.getByRole("button", { name: "加载更多" });
    fireEvent.click(button);
    expect(onLoadMore).toHaveBeenCalledTimes(1);

    rerender(
      <BacktestHistory
        {...baseProps}
        runs={[makeRun()]}
        hasMore={false}
        isLoadingMore={false}
        onLoadMore={onLoadMore}
      />,
    );
    expect(screen.queryByRole("button", { name: "加载更多" })).not.toBeInTheDocument();
  });

  it("supports multi-selection and opens backtest runs comparator modal", async () => {
    const run1 = makeRun({
      id: "run-1",
      name: "策略1",
      summary_metrics: {
        total_return: 10,
        annualized_return: 12,
        annualized_volatility: 15,
        max_drawdown: -5,
        trade_count: 5,
        turnover_rate: 50,
      },
    });
    const run2 = makeRun({
      id: "run-2",
      name: "策略2",
      summary_metrics: {
        total_return: 20,
        annualized_return: 25,
        annualized_volatility: 18,
        max_drawdown: -8,
        trade_count: 10,
        turnover_rate: 80,
      },
    });

    render(<BacktestHistory {...baseProps} runs={[run1, run2]} />);

    const compareBtn = screen.getByRole("button", { name: "横向对比已选回测" });
    expect(compareBtn).toBeDisabled();

    // 勾选两个回测
    const checkbox1 = screen.getByRole("checkbox", { name: "选择对比 策略1" });
    const checkbox2 = screen.getByRole("checkbox", { name: "选择对比 策略2" });
    fireEvent.click(checkbox1);
    fireEvent.click(checkbox2);

    expect(compareBtn).toBeEnabled();
    expect(screen.getByText("横向对比 (2)")).toBeInTheDocument();

    // 点击横向对比打开弹窗
    fireEvent.click(compareBtn);
    expect(await screen.findByText("策略回测多维横向对比")).toBeInTheDocument();
    expect(screen.getByText("2 个回测样本")).toBeInTheDocument();

    // 点击清空对比
    fireEvent.click(screen.getByRole("button", { name: "清空对比" }));
    expect(screen.getByRole("button", { name: "横向对比已选回测" })).toBeDisabled();
  });
});
