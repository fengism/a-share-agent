import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import { useAuthStore } from "../../store/authStore";
import QuantPage from ".";

const run = {
  id: "run-one",
  name: "双均线测试",
  status: "succeeded" as const,
  attempts: 1,
  created_at: 1_786_000_000,
  updated_at: 1_786_000_010,
  completed_at: 1_786_000_010,
  request: {
    name: "双均线测试",
    universe: { source: "custom" as const, codes: ["600519"] },
    strategy: {
      type: "ma_cross" as const,
      version: "1.0.0",
      name: "双均线趋势",
      parameters: { fast_period: 5, slow_period: 20 },
    },
    start_date: "2025-01-01",
    end_date: "2026-01-01",
    benchmark: "000300",
  },
  result: {
    engine_version: "v1",
    data_hash: "hash",
    data_sources: ["akshare"],
    codes: ["600519"],
    metrics: {
      total_return: 12,
      annualized_return: 12,
      annualized_volatility: 10,
      max_drawdown: -5,
      turnover_rate: 100,
      trade_count: 2,
    },
    equity_curve: [],
    monthly_returns: [],
    trades: [],
  },
};

const secondRun = {
  ...run,
  id: "run-two",
  name: "动量测试",
  request: {
    ...run.request,
    name: "动量测试",
    strategy: {
      type: "momentum_breakout" as const,
      version: "1.0.0",
      name: "动量突破",
      parameters: { lookback_period: 20 },
    },
  },
};

const missingRunError = new ApiError(404, "/quant/backtests/missing", "回测记录不存在");

vi.mock("../../api/queries", () => ({
  useQuantStrategyPresets: () => ({ data: [] }),
  useSavedQuantStrategies: () => ({ data: [], isLoading: false }),
  useSaveQuantStrategy: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useDeleteQuantStrategy: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useCreateQuantBacktest: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useQuantBacktests: () => ({
    data: { pages: [{ items: [run, secondRun] }] },
    hasNextPage: false,
    isLoading: false,
    isFetching: false,
    isFetchingNextPage: false,
    refetch: vi.fn(),
    fetchNextPage: vi.fn(),
  }),
  useQuantBacktest: (runId?: string) => ({
    data: [run, secondRun].find((item) => item.id === runId),
    error: runId === "missing" ? missingRunError : undefined,
  }),
  useCancelQuantBacktest: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useRetryQuantBacktest: () => ({ mutateAsync: vi.fn(), isPending: false, variables: undefined }),
  useDeleteQuantBacktest: () => ({ mutateAsync: vi.fn(), isPending: false, variables: undefined }),
  useQuantStrategyDrafts: () => ({ data: [], isLoading: false }),
  useQuantStrategyRegistryStatus: () => ({ data: undefined }),
  useGenerateQuantStrategyDraft: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateQuantStrategyDraft: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useValidateQuantStrategyDraft: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useBacktestQuantStrategyDraft: () => ({ mutateAsync: vi.fn(), isPending: false }),
  usePublishQuantStrategyDraft: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock("./BacktestResultSection", () => ({
  default: ({ run: selectedRun }: { run?: typeof run }) => (
    <section aria-label="回测结果分析">
      {selectedRun?.result ? "回测结果已渲染" : "暂无回测结果"}
    </section>
  ),
}));

describe("Quant page", () => {
  beforeEach(() => {
    useAuthStore.setState({
      user: { id: 1, username: "alice", is_admin: false, must_change_password: false },
      bootstrapped: true,
    });
  });

  it("splits configuration, task history, and result analysis into separate views", async () => {
    render(
      <MemoryRouter>
        <QuantPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "量化研究" })).toBeInTheDocument();
    expect(screen.getByText("策略实验室")).toBeInTheDocument();
    expect(screen.queryByLabelText("回测能力")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("量化研究流程")).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "量化回测配置" })).toBeInTheDocument();
    expect(screen.getByText("策略与回测参数")).toBeInTheDocument();

    expect(screen.queryByText("历史回测")).not.toBeInTheDocument();
    expect(screen.queryByText("回测结果已渲染")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: /任务记录/ }));
    expect(screen.getByText("历史回测")).toBeInTheDocument();
    expect(screen.getByText("当前回测")).toBeInTheDocument();
    expect(screen.getAllByText("双均线测试").length).toBeGreaterThan(0);
    const taskColumns = screen.getByText("当前回测").closest(".ant-card")?.parentElement;
    expect(taskColumns).toHaveClass("quant-task-columns");
    expect(taskColumns).toContainElement(screen.getByText("历史回测").closest(".ant-card"));
    expect(screen.getByRole("tab", { name: /结果分析.*可查看/ })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "查看回测 双均线测试" }));
    expect(screen.getByRole("region", { name: "回测结果分析" })).toBeInTheDocument();
    expect(await screen.findByText("回测结果已渲染")).toBeInTheDocument();
  });

  it("restores and updates the selected run through the URL", async () => {
    function LocationProbe() {
      return <div data-testid="location-search">{useLocation().search}</div>;
    }

    render(
      <MemoryRouter initialEntries={["/?run=run-two&panel=runs"]}>
        <QuantPage />
        <LocationProbe />
      </MemoryRouter>,
    );

    expect(screen.getByRole("button", { name: "查看回测 动量测试" })).toHaveAttribute("aria-current", "true");
    expect(screen.getByTestId("location-search")).toHaveTextContent("run=run-two");
    expect(screen.getByTestId("location-search")).toHaveTextContent("panel=runs");

    fireEvent.click(screen.getByRole("button", { name: "查看回测 双均线测试" }));
    await waitFor(() => expect(screen.getByTestId("location-search")).toHaveTextContent("run=run-one"));
  });

  it("falls back to the latest run when a shared URL no longer exists", async () => {
    function LocationProbe() {
      return <div data-testid="location-search">{useLocation().search}</div>;
    }

    render(
      <MemoryRouter initialEntries={["/?run=missing&panel=runs"]}>
        <QuantPage />
        <LocationProbe />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByTestId("location-search")).toHaveTextContent("run=run-one"));
    expect(screen.getByRole("button", { name: "查看回测 双均线测试" })).toHaveAttribute("aria-current", "true");
  });

  it("loads the online strategy workbench only after an administrator selects it", async () => {
    useAuthStore.setState({
      user: { id: 1, username: "admin", is_admin: true, must_change_password: false },
    });

    function LocationProbe() {
      return <div data-testid="location-search">{useLocation().search}</div>;
    }

    render(
      <MemoryRouter>
        <QuantPage />
        <LocationProbe />
      </MemoryRouter>,
    );

    expect(screen.queryByRole("region", { name: "在线策略生成工作台" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("回测名称"), { target: { value: "未提交回测参数" } });

    fireEvent.click(screen.getByRole("tab", { name: /在线策略/ }));

    expect(await screen.findByRole("region", { name: "在线策略生成工作台" }, { timeout: 10000 })).toBeInTheDocument();
    expect(screen.getByText("生成受限策略草稿")).toBeInTheDocument();
    expect(screen.getByTestId("location-search")).toHaveTextContent("view=authoring");
    fireEvent.change(screen.getByPlaceholderText(/例如：使用 20 日和 60 日均线/), {
      target: { value: "尚未提交的在线策略提示词" },
    });

    fireEvent.click(screen.getByRole("tab", { name: /回测实验/ }));
    expect(screen.getByLabelText("回测名称")).toHaveValue("未提交回测参数");

    fireEvent.click(screen.getByRole("tab", { name: /在线策略/ }));
    expect(screen.getByPlaceholderText(/例如：使用 20 日和 60 日均线/))
      .toHaveValue("尚未提交的在线策略提示词");
  });

  it("keeps the authoring deep link for regular users but hides publish controls", async () => {
    function LocationProbe() {
      return <div data-testid="location-search">{useLocation().search}</div>;
    }

    render(
      <MemoryRouter initialEntries={["/?view=authoring&run=run-two"]}>
        <QuantPage />
        <LocationProbe />
      </MemoryRouter>,
    );

    // 在线策略对普通用户开放：URL 参数保留，工作台正常渲染
    expect(await screen.findByRole("region", { name: "在线策略生成工作台" }, { timeout: 10000 })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("location-search")).toHaveTextContent("view=authoring"));
    expect(screen.getByTestId("location-search")).toHaveTextContent("run=run-two");

    // 但「发布策略」是管理员能力，普通用户看不到
    expect(screen.queryByRole("button", { name: /发布策略/ })).not.toBeInTheDocument();
    expect(screen.queryByText("管理员能力")).not.toBeInTheDocument();
    expect(screen.getByText("策略实验")).toBeInTheDocument();
  });

  it("shows publish controls to administrators", async () => {
    useAuthStore.setState({
      user: { id: 1, username: "admin", is_admin: true, must_change_password: false },
    });

    render(
      <MemoryRouter initialEntries={["/?view=authoring"]}>
        <QuantPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("region", { name: "在线策略生成工作台" }, { timeout: 10000 })).toBeInTheDocument();
    expect(screen.getByText("管理员能力")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /发布策略/ })).toBeInTheDocument();
  });
});
