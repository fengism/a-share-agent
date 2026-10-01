import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import dayjs from "dayjs";
import { describe, expect, it, vi } from "vitest";
import MarketDailyBarManagerCard from "./MarketDailyBarManagerCard";

const mocks = vi.hoisted(() => ({
  refreshMutate: vi.fn(),
  deleteMutate: vi.fn(),
  factorRefreshMutate: vi.fn(),
  factorInvalidateMutate: vi.fn(),
  refetch: vi.fn(),
  factorRefetch: vi.fn(),
}));

vi.mock("../../api/queries", () => ({
  useMarketDailyRefreshHistory: () => ({
    data: {
      items: [{
        trade_date: dayjs().format("YYYY-MM-DD"),
        checkpoint: "recheck",
        segment: "cn_stock",
        status: "failed",
        attempts: 2,
        next_retry_at: null,
        expected_count: null,
        stored_count: null,
        last_error: "temporary",
        started_at: null,
        completed_at: null,
      }],
    },
    isFetching: false,
    refetch: mocks.refetch,
  }),
  useRefreshMarketDailyBars: () => ({ mutate: mocks.refreshMutate, isPending: false }),
  useDeleteMarketDailyBars: () => ({ mutate: mocks.deleteMutate, isPending: false }),
  useMarketAdjustmentFactorStatus: () => ({
    data: {
      code: "600519",
      status: "degraded",
      bar_count: 2,
      factor_count: 2,
      action_count: 1,
      first_bar_date: "2026-09-29",
      last_bar_date: "2026-09-30",
      first_factor_date: "2026-09-29",
      last_factor_date: "2026-09-30",
      action_hash: "hash",
      algorithm_version: "algo-v1",
      source: "tdxhub",
      calculated_at: "2026-09-30T09:00:00Z",
      last_checked_at: "2026-09-30T09:05:00Z",
      last_error: "xdxr offline",
      using_last_good: true,
      coverage_complete: true,
    },
    isFetching: false,
    refetch: mocks.factorRefetch,
  }),
  useRefreshMarketAdjustmentFactor: () => ({ mutate: mocks.factorRefreshMutate, isPending: false }),
  useInvalidateMarketAdjustmentFactor: () => ({ mutate: mocks.factorInvalidateMutate, isPending: false }),
}));

describe("MarketDailyBarManagerCard", () => {
  it("saves config and triggers failed-only refresh", () => {
    const onChange = vi.fn();
    const onSave = vi.fn();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MarketDailyBarManagerCard
          form={{
            market_daily_bar_refresh_enabled: true,
            market_daily_bar_refresh_poll_seconds: 60,
            market_daily_bar_refresh_retry_base_seconds: 60,
  market_daily_observation_retention_days: 1095,
  market_daily_attempt_retention_days: 1095,
          }}
          onChange={onChange}
          onSave={onSave}
          isSaving={false}
          sectionTitleStyle={{}}
        />
      </QueryClientProvider>,
    );

    expect(screen.getByText("实时行情由行情页面自动拉取")).toBeInTheDocument();
    expect(screen.getByText(/不会把盘中价格写入日线库/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "保存归档配置" }));
    expect(onSave).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByText("仅重试失败").closest("button")!);
    expect(mocks.refreshMutate).toHaveBeenCalledWith(
      expect.objectContaining({
        checkpoint: "recheck",
        retry_failed_only: true,
        segments: ["cn_stock", "cn_index", "hk_stock", "hk_index"],
      }),
      expect.any(Object),
    );
    expect(screen.getByText("temporary")).toBeInTheDocument();
    expect(screen.getByText("使用 last-good")).toBeInTheDocument();
    expect(screen.getByText("xdxr offline")).toBeInTheDocument();
    fireEvent.click(screen.getByText("强制复核 XDXR").closest("button")!);
    expect(mocks.factorRefreshMutate).toHaveBeenCalledWith("600519", expect.any(Object));
    client.clear();
  });
});
