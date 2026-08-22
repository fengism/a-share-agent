import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import BacktestForm from "./BacktestForm";

const mocks = vi.hoisted(() => ({
  createRun: vi.fn(),
  saveStrategy: vi.fn(),
  deleteStrategy: vi.fn(),
  presets: [] as Array<Record<string, unknown>>,
  savedStrategies: [] as Array<{
    id: number;
    name: string;
    config: {
      type: string;
      version?: string;
      parameters: Record<string, number | boolean | string>;
    };
  }>,
}));

vi.mock("../../api/queries", () => ({
  useQuantStrategyPresets: () => ({ data: mocks.presets }),
  useSavedQuantStrategies: () => ({ data: mocks.savedStrategies, isLoading: false }),
  useSaveQuantStrategy: () => ({ mutateAsync: mocks.saveStrategy, isPending: false }),
  useDeleteQuantStrategy: () => ({ mutateAsync: mocks.deleteStrategy, isPending: false }),
  useCreateQuantBacktest: () => ({ mutateAsync: mocks.createRun, isPending: false }),
}));

function selectStrategy(name: RegExp) {
  const changeButton = screen.queryByRole("button", { name: "更换策略" });
  if (changeButton) fireEvent.click(changeButton);
  fireEvent.click(screen.getByRole("radio", { name }));
}

describe("BacktestForm", () => {
  beforeEach(() => {
    mocks.createRun.mockReset().mockResolvedValue({ id: "new-run" });
    mocks.saveStrategy.mockReset();
    mocks.deleteStrategy.mockReset();
    mocks.presets.length = 0;
    mocks.savedStrategies.length = 0;
  });

  it("groups the workflow and switches strategy-specific fields", async () => {
    render(<BacktestForm onCreated={vi.fn()} />);

    expect(screen.getByText("1. 回测范围")).toBeInTheDocument();
    expect(screen.getByText("2. 策略参数")).toBeInTheDocument();
    expect(screen.getByText("3. 执行设置")).toBeInTheDocument();
    expect(screen.getByLabelText("短均线")).toBeInTheDocument();

    selectStrategy(/RSI 均值回归/);

    expect(await screen.findByLabelText("RSI 周期")).toBeInTheDocument();
    expect(screen.getByText("当前策略：RSI 均值回归")).toBeInTheDocument();
    expect(screen.getByLabelText("买入阈值")).toBeInTheDocument();
    expect(screen.getByLabelText("卖出阈值")).toBeInTheDocument();
    expect(screen.queryByLabelText("短均线")).not.toBeInTheDocument();
  });

  it("prefills a custom universe from selected screener stocks", () => {
    render(<BacktestForm initialCodes={["600519", "000001"]} onCreated={vi.fn()} />);

    expect(screen.getByPlaceholderText("600519, 000001")).toHaveValue("600519, 000001");
    expect(screen.getByPlaceholderText("例如：消费龙头双均线")).toHaveValue("双均线趋势 · 2只股票回测");
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
      strategy: {
        type: "ma_cross",
        version: "1.0.0",
        parameters: { fast_period: 5, slow_period: 20 },
      },
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
    fireEvent.click(screen.getByRole("button", { name: /策略配置管理/ }));
    fireEvent.click(screen.getByRole("button", { name: "恢复默认参数" }));

    expect(screen.getByLabelText("回测名称")).toHaveValue("双均线趋势 · 600519回测");
    expect(screen.getByLabelText("股票代码")).toHaveValue("600519");
  });

  it("renders parameter controls from an API strategy descriptor", async () => {
    mocks.presets.push({
      key: "volume_filter",
      version: "1.0.0",
      definition_hash: "sha256:custom",
      name: "成交量过滤",
      description: "按成交量条件过滤信号",
      scenario: "放量行情",
      risk_level: "medium",
      presentation: { icon: "unknown" },
      constraints: [],
      parameters: [
        { key: "enabled", type: "boolean", label: "启用过滤", description: "", default: true },
        { key: "mode", type: "string", label: "过滤模式", description: "", default: "strict", choices: ["strict", "loose"] },
      ],
      config: { type: "volume_filter", version: "1.0.0", parameters: { enabled: true, mode: "strict" } },
    });
    render(<BacktestForm onCreated={vi.fn()} />);

    selectStrategy(/成交量过滤/);

    expect(await screen.findByLabelText("启用过滤")).toBeChecked();
    expect(screen.getByRole("combobox", { name: "过滤模式" })).toBeInTheDocument();
  });

  it("blocks submission using constraints from a custom strategy descriptor", async () => {
    mocks.presets.push({
      key: "custom_window",
      version: "1.0.0",
      definition_hash: "sha256:custom-window",
      name: "自定义窗口",
      description: "验证动态参数关系",
      scenario: "测试行情",
      risk_level: "medium",
      presentation: { icon: "unknown" },
      parameters: [
        { key: "entry_window", type: "integer", label: "入场窗口", description: "", default: 5, minimum: 1, maximum: 100 },
        { key: "exit_window", type: "integer", label: "离场窗口", description: "", default: 20, minimum: 1, maximum: 100 },
      ],
      constraints: [{
        operator: "less_than",
        left: "$entry_window",
        right: "$exit_window",
        message: "入场窗口必须小于离场窗口",
      }],
      config: { type: "custom_window", version: "1.0.0", parameters: { entry_window: 5, exit_window: 20 } },
    });
    render(<BacktestForm onCreated={vi.fn()} />);

    selectStrategy(/自定义窗口/);
    fireEvent.change(await screen.findByLabelText("入场窗口"), { target: { value: "30" } });
    fireEvent.change(screen.getByLabelText("离场窗口"), { target: { value: "20" } });
    fireEvent.click(screen.getByRole("button", { name: "开始回测" }));

    expect((await screen.findAllByText("入场窗口必须小于离场窗口")).length).toBeGreaterThan(0);
    expect(mocks.createRun).not.toHaveBeenCalled();
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
    expect(screen.getByLabelText("佣金（BP）").closest(".quant-advanced-execution-fields"))
      .toHaveClass("ant-row-bottom");
  });

  it("confirms before deleting a saved strategy", async () => {
    mocks.savedStrategies.push({
      id: 7,
      name: "已保存 RSI",
      config: {
        type: "rsi_reversion",
        version: "1.0.0",
        parameters: { rsi_period: 9, buy_threshold: 25, sell_threshold: 75 },
      },
    });
    mocks.deleteStrategy.mockResolvedValue({ deleted: true });
    render(<BacktestForm onCreated={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: /策略配置管理/ }));
    fireEvent.mouseDown(screen.getByRole("combobox", { name: "已保存策略" }));
    fireEvent.click(await screen.findByText("已保存 RSI"));
    fireEvent.click(screen.getByRole("button", { name: "删除已保存策略" }));

    expect(mocks.deleteStrategy).not.toHaveBeenCalled();
    expect(await screen.findByText("删除已保存策略“已保存 RSI”？")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /^删\s*除$/ }));
    await waitFor(() => expect(mocks.deleteStrategy).toHaveBeenCalledWith(7));
  });

  it("submits the selected non-default strategy instead of ma_cross", async () => {
    render(<BacktestForm onCreated={vi.fn()} />);

    selectStrategy(/RSI 均值回归/);
    expect(await screen.findByLabelText("RSI 周期")).toBeInTheDocument();
    expect(screen.getByLabelText("回测名称")).toHaveValue("RSI 均值回归 · 600519回测");
    fireEvent.click(screen.getByRole("button", { name: "开始回测" }));

    await waitFor(() => expect(mocks.createRun).toHaveBeenCalledTimes(1));
    expect(mocks.createRun).toHaveBeenCalledWith(expect.objectContaining({
      name: "RSI 均值回归 · 600519回测",
      strategy: {
        type: "rsi_reversion",
        version: "1.0.0",
        parameters: { rsi_period: 14, buy_threshold: 30, sell_threshold: 70 },
      },
    }));
  });


  it("preserves a user-entered run name when switching presets", async () => {
    render(<BacktestForm onCreated={vi.fn()} />);

    fireEvent.change(screen.getByLabelText("回测名称"), { target: { value: "我的震荡实验" } });
    selectStrategy(/RSI 均值回归/);

    expect(await screen.findByLabelText("RSI 周期")).toBeInTheDocument();
    expect(screen.getByLabelText("回测名称")).toHaveValue("我的震荡实验");
  });

  it("keeps saved strategy management collapsed by default and reflects edited parameters", async () => {
    mocks.savedStrategies.push({
      id: 8,
      name: "已保存 RSI 参数",
      config: {
        type: "rsi_reversion",
        version: "1.0.0",
        parameters: { rsi_period: 9, buy_threshold: 25, sell_threshold: 75 },
      },
    });
    render(<BacktestForm onCreated={vi.fn()} />);

    expect(screen.queryByRole("combobox", { name: "已保存策略" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /策略配置管理/ }));
    expect(screen.getByRole("combobox", { name: "已保存策略" })).toBeInTheDocument();
    fireEvent.mouseDown(screen.getByRole("combobox", { name: "已保存策略" }));
    fireEvent.click(await screen.findByText("已保存 RSI 参数"));

    expect(await screen.findByText("实际参数：RSI 周期 9 · 买入阈值 25 · 卖出阈值 75")).toBeInTheDocument();
    expect(screen.getByText("已修改")).toBeInTheDocument();
  });

});
