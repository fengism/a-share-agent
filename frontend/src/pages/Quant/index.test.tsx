import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
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
    strategy: { ...run.request.strategy, type: "momentum_breakout" as const },
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
    data: { items: [run, secondRun] },
    isLoading: false,
    isFetching: false,
    refetch: vi.fn(),
  }),
  useQuantBacktest: (runId?: string) => ({
    data: [run, secondRun].find((item) => item.id === runId),
    error: runId === "missing" ? missingRunError : undefined,
  }),
  useCancelQuantBacktest: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useRetryQuantBacktest: () => ({ mutateAsync: vi.fn(), isPending: false, variables: undefined }),
  useDeleteQuantBacktest: () => ({ mutateAsync: vi.fn(), isPending: false, variables: undefined }),
}));

vi.mock("./BacktestResult", () => ({
  default: () => <div>回测结果已渲染</div>,
}));

describe("Quant page", () => {
  it("renders strategy controls, completed result and history", () => {
    render(
      <MemoryRouter>
        <QuantPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "量化研究" })).toBeInTheDocument();
    expect(screen.getByText("策略与回测参数")).toBeInTheDocument();
    expect(screen.getByText("回测结果已渲染")).toBeInTheDocument();
    expect(screen.getByText("历史回测")).toBeInTheDocument();
    expect(screen.getByText("当前回测")).toBeInTheDocument();
    expect(screen.getAllByText("双均线测试").length).toBeGreaterThan(0);
  });

  it("restores and updates the selected run through the URL", async () => {
    function LocationProbe() {
      return <div data-testid="location-search">{useLocation().search}</div>;
    }

    render(
      <MemoryRouter initialEntries={["/?run=run-two"]}>
        <QuantPage />
        <LocationProbe />
      </MemoryRouter>,
    );

    expect(screen.getByRole("button", { name: "查看回测 动量测试" })).toHaveAttribute("aria-current", "true");
    expect(screen.getByTestId("location-search")).toHaveTextContent("?run=run-two");

    fireEvent.click(screen.getByRole("button", { name: "查看回测 双均线测试" }));
    await waitFor(() => expect(screen.getByTestId("location-search")).toHaveTextContent("?run=run-one"));
  });

  it("falls back to the latest run when a shared URL no longer exists", async () => {
    function LocationProbe() {
      return <div data-testid="location-search">{useLocation().search}</div>;
    }

    render(
      <MemoryRouter initialEntries={["/?run=missing"]}>
        <QuantPage />
        <LocationProbe />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByTestId("location-search")).toHaveTextContent("?run=run-one"));
    expect(screen.getByRole("button", { name: "查看回测 双均线测试" })).toHaveAttribute("aria-current", "true");
  });
});
