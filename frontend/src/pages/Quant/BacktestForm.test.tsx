import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import BacktestForm from "./BacktestForm";

const mocks = vi.hoisted(() => ({
  createRun: vi.fn(),
  saveStrategy: vi.fn(),
  deleteStrategy: vi.fn(),
  savedStrategies: [] as Array<{
    id: number;
    name: string;
    config: {
      type: "ma_cross" | "momentum_breakout" | "rsi_reversion";
      fast_period: number;
      slow_period: number;
      lookback_period: number;
      rsi_period: number;
      buy_threshold: number;
      sell_threshold: number;
    };
  }>,
}));

vi.mock("../../api/queries", () => ({
  useQuantStrategyPresets: () => ({ data: [] }),
  useSavedQuantStrategies: () => ({ data: mocks.savedStrategies, isLoading: false }),
  useSaveQuantStrategy: () => ({ mutateAsync: mocks.saveStrategy, isPending: false }),
  useDeleteQuantStrategy: () => ({ mutateAsync: mocks.deleteStrategy, isPending: false }),
  useCreateQuantBacktest: () => ({ mutateAsync: mocks.createRun, isPending: false }),
}));

describe("BacktestForm", () => {
  beforeEach(() => {
    mocks.createRun.mockReset().mockResolvedValue({ id: "new-run" });
    mocks.saveStrategy.mockReset();
    mocks.deleteStrategy.mockReset();
    mocks.savedStrategies.length = 0;
  });

  it("groups the workflow and switches strategy-specific fields", async () => {
    render(<BacktestForm onCreated={vi.fn()} />);

    expect(screen.getByText("1. 回测范围")).toBeInTheDocument();
    expect(screen.getByText("2. 策略参数")).toBeInTheDocument();
    expect(screen.getByText("3. 执行设置")).toBeInTheDocument();
    expect(screen.getByLabelText("短均线")).toBeInTheDocument();

    const rsiPreset = screen.getByRole("radio", { name: /RSI 均值回归/ });
    fireEvent.click(rsiPreset);

    expect(await screen.findByLabelText("RSI 周期")).toBeInTheDocument();
    expect(rsiPreset).toHaveAttribute("aria-checked", "true");
    expect(screen.getByText("RSI 进入超卖区间后买入，进入超买区间后退出。")).toBeInTheDocument();
    expect(screen.getByLabelText("买入阈值")).toBeInTheDocument();
    expect(screen.getByLabelText("卖出阈值")).toBeInTheDocument();
    expect(screen.queryByLabelText("短均线")).not.toBeInTheDocument();
  });

  it("disables custom codes when the current portfolio is selected", async () => {
    render(<BacktestForm onCreated={vi.fn()} />);

    fireEvent.mouseDown(screen.getByRole("combobox", { name: "股票池" }));
    fireEvent.click(await screen.findByText("当前持仓"));

    await waitFor(() => expect(screen.getByLabelText("股票代码")).toBeDisabled());
    expect(screen.getByText("运行时读取当前持仓股票，最多 10 只")).toBeInTheDocument();
  });

  it("keeps the existing request contract when submitting", async () => {
    const onCreated = vi.fn();
    render(<BacktestForm onCreated={onCreated} />);

    fireEvent.change(screen.getByLabelText("回测名称"), { target: { value: "  消费策略  " } });
    fireEvent.change(screen.getByLabelText("股票代码"), { target: { value: "600519， 000001  " } });
    fireEvent.click(screen.getByRole("button", { name: "开始回测" }));

    await waitFor(() => expect(mocks.createRun).toHaveBeenCalledTimes(1));
    expect(mocks.createRun).toHaveBeenCalledWith(expect.objectContaining({
      name: "消费策略",
      universe: { source: "custom", codes: ["600519", "000001"] },
      strategy: expect.objectContaining({ type: "ma_cross", fast_period: 5, slow_period: 20 }),
      execution: expect.objectContaining({
        initial_cash: 1_000_000,
        commission_rate: 0.0003,
        minimum_commission: 5,
        stamp_duty_rate: 0.0005,
        transfer_fee_rate: 0.00001,
        slippage_bps: 5,
        lot_size: 100,
        risk_free_rate: 0.015,
      }),
      benchmark: "000300",
    }));
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith({ id: "new-run" }));
  });

  it("blocks submission when the stock universe exceeds the backend limit", async () => {
    const elevenCodes = Array.from({ length: 11 }, (_, index) => String(600000 + index)).join(",");
    render(<BacktestForm onCreated={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("股票代码"), { target: { value: elevenCodes } });
    fireEvent.click(screen.getByRole("button", { name: "开始回测" }));

    expect(await screen.findByText("股票池最多支持 10 只股票")).toBeInTheDocument();
    expect(mocks.createRun).not.toHaveBeenCalled();
  });

  it("resets edited values to the default configuration", () => {
    render(<BacktestForm onCreated={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("回测名称"), { target: { value: "临时配置" } });
    fireEvent.click(screen.getByRole("button", { name: "恢复默认参数" }));

    expect(screen.getByLabelText("回测名称")).toHaveValue("双均线回测");
    expect(screen.getByLabelText("股票代码")).toHaveValue("600519");
  });

  it("reveals advanced execution assumptions on demand", () => {
    render(<BacktestForm onCreated={vi.fn()} />);

    expect(screen.queryByLabelText("佣金（BP）")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("高级执行参数"));

    expect(screen.getByLabelText("佣金（BP）")).toHaveDisplayValue("3.0");
    expect(screen.getByLabelText("最低佣金（元）")).toHaveValue("5");
    expect(screen.getByLabelText("印花税（BP）")).toHaveDisplayValue("5.0");
    expect(screen.getByLabelText("过户费（BP）")).toHaveDisplayValue("0.10");
    expect(screen.getByLabelText("交易单位（股）")).toHaveValue("100");
    expect(screen.getByLabelText("无风险利率（%）")).toHaveDisplayValue("1.5");
  });

  it("confirms before deleting a saved strategy", async () => {
    mocks.savedStrategies.push({
      id: 7,
      name: "已保存 RSI",
      config: {
        type: "rsi_reversion",
        fast_period: 5,
        slow_period: 20,
        lookback_period: 20,
        rsi_period: 9,
        buy_threshold: 25,
        sell_threshold: 75,
      },
    });
    mocks.deleteStrategy.mockResolvedValue({ deleted: true });
    render(<BacktestForm onCreated={vi.fn()} />);

    fireEvent.mouseDown(screen.getByRole("combobox", { name: "已保存策略" }));
    fireEvent.click(await screen.findByText("已保存 RSI"));
    fireEvent.click(screen.getByRole("button", { name: "删除已保存策略" }));

    expect(mocks.deleteStrategy).not.toHaveBeenCalled();
    expect(await screen.findByText("删除已保存策略“已保存 RSI”？")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^删\s*除$/ }));
    await waitFor(() => expect(mocks.deleteStrategy).toHaveBeenCalledWith(7));
  });
});
