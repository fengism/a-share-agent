import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { QuantBacktestRun } from "../../api/queries";
import BacktestRunsComparatorModal from "./BacktestRunsComparatorModal";

function makeRun(id: string, name: string, totalReturn: number, sharpe: number, maxDd: number, winRate: number): QuantBacktestRun {
  return {
    id,
    name,
    status: "succeeded",
    attempts: 1,
    created_at: 1_786_000_000,
    updated_at: 1_786_000_010,
    completed_at: 1_786_000_010,
    request: {
      name,
      universe: { source: "custom", codes: ["600519", "000858"] },
      strategy: {
        type: "ma_cross",
        version: "1.0.0",
        name: "双均线策略",
        parameters: { fast_period: 5, slow_period: 20 },
      },
      start_date: "2025-01-01",
      end_date: "2026-01-01",
      benchmark: "000300",
    },
    summary_metrics: {
      total_return: totalReturn,
      annualized_return: totalReturn * 1.1,
      annualized_volatility: 18.5,
      max_drawdown: maxDd,
      sharpe_ratio: sharpe,
      win_rate: winRate,
      profit_loss_ratio: 1.85,
      trade_count: 12,
      turnover_rate: 15.2,
    },
  };
}

describe("BacktestRunsComparatorModal", () => {
  it("renders comparison table and highlights winners across multiple runs", () => {
    const runA = makeRun("run-a", "双均线稳健型", 15.6, 1.45, -8.2, 58.3);
    const runB = makeRun("run-b", "布林带激进型", 28.4, 1.25, -14.6, 62.5);

    const onSelectRun = vi.fn();
    const onClose = vi.fn();

    render(
      <BacktestRunsComparatorModal
        open
        runs={[runA, runB]}
        onClose={onClose}
        onSelectRun={onSelectRun}
      />,
    );

    // 检查标题与回测名称
    expect(screen.getByText("策略回测多维横向对比")).toBeInTheDocument();
    expect(screen.getByText("2 个回测样本")).toBeInTheDocument();
    expect(screen.getAllByText("双均线稳健型").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("布林带激进型").length).toBeGreaterThanOrEqual(1);

    // 亮点卡片检查
    expect(screen.getByText("累计收益冠军")).toBeInTheDocument();
    expect(screen.getAllByText("+28.4%").length).toBeGreaterThanOrEqual(1); // runB 收益最高
    expect(screen.getByText("最优夏普比率")).toBeInTheDocument();
    expect(screen.getAllByText("1.45").length).toBeGreaterThanOrEqual(1); // runA 夏普最高
    expect(screen.getByText("最小最大回撤")).toBeInTheDocument();
    expect(screen.getAllByText("-8.2%").length).toBeGreaterThanOrEqual(1); // runA 回撤最小

    // 点击查看回测
    const viewButtons = screen.getAllByRole("button", { name: "查看此回测 →" });
    expect(viewButtons).toHaveLength(2);
    fireEvent.click(viewButtons[0]);
    expect(onSelectRun).toHaveBeenCalledWith("run-a");
    expect(onClose).toHaveBeenCalled();
  });

  it("handles empty or insufficient runs gracefully", () => {
    const runA = makeRun("run-a", "单回测", 10.0, 1.0, -5.0, 50.0);
    render(
      <BacktestRunsComparatorModal
        open
        runs={[runA]}
        onClose={vi.fn()}
        onSelectRun={vi.fn()}
      />,
    );
    expect(
      screen.getByText("请在历史记录中至少勾选 2 个已成功完成的回测任务进行横向对比"),
    ).toBeInTheDocument();
  });

  it("copies markdown comparison table to clipboard", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: {
        writeText,
      },
    });

    const runA = makeRun("run-a", "策略A", 12.0, 1.2, -6.0, 55.0);
    const runB = makeRun("run-b", "策略B", 18.0, 1.5, -9.0, 60.0);

    render(
      <BacktestRunsComparatorModal
        open
        runs={[runA, runB]}
        onClose={vi.fn()}
        onSelectRun={vi.fn()}
      />,
    );

    const copyBtn = screen.getByRole("button", { name: /复制 Markdown 对比表/ });
    fireEvent.click(copyBtn);

    expect(writeText).toHaveBeenCalledTimes(1);
    const copiedContent = writeText.mock.calls[0][0];
    expect(copiedContent).toContain("# 策略回测横向对比研报");
    expect(copiedContent).toContain("策略A");
    expect(copiedContent).toContain("策略B");
  });
});
