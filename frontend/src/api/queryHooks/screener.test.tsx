import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { PropsWithChildren } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../client", () => ({
  API_TIMEOUTS: {
    DEFAULT: 15_000,
    EXTERNAL: 120_000,
    SCREENER: 300_000,
    LONG_RUNNING: 300_000,
  },
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));
vi.mock("../sse", () => ({
  streamScreenerStrategy: vi.fn(),
}));

import { apiPost } from "../client";
import { streamScreenerStrategy } from "../sse";
import { useRunScreenerStrategy, useScreenerScreen } from "./screener";
import type { ScreenerStrategyResult } from "../../types/stock";

const strategyResult: ScreenerStrategyResult = {
  strategy_key: "bull_trend",
  strategy_name: "多头趋势",
  strategy_version: "1.0.0",
  definition_hash: "sha256:test",
  parameters: {},
  matches: [],
  matched_codes: [],
  evaluated: 0,
  failed: {},
  excluded: {},
};

const candidateStock = {
  code: "000001",
  name: "平安银行",
  price: 12,
  change_pct: 1,
  pe_ttm: 6,
  pb: 0.7,
  market_cap: 2800,
  turnover_pct: 1.2,
  volume: 1000,
  second_industry: null,
};

function createWrapper() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((resolver) => { resolve = resolver; });
  return { promise, resolve };
}

describe("useRunScreenerStrategy", () => {

  it("deduplicates screener API items by normalized stock code", async () => {
    vi.mocked(apiPost).mockResolvedValue({
      items: [
        { ...candidateStock, code: "688836", name: "N宇树" },
        { ...candidateStock, code: "sh688836", name: "N宇树" },
        { ...candidateStock, code: " 688836 ", name: "N宇树" },
      ],
      total: 3,
      page: 1,
      page_size: 50,
    });
    const filters = { page: 1, page_size: 50, sort_by: "market_cap", sort_order: "desc" } as const;
    const { result } = renderHook(() => useScreenerScreen(filters), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.items).toEqual([
      expect.objectContaining({ code: "688836", name: "N宇树" }),
    ]);
    expect(result.current.data?.total).toBe(1);
    expect(apiPost).toHaveBeenCalledWith(
      "/screener/screen",
      filters,
      { timeoutMs: 300_000 },
    );
  });

  it("returns each matched strategy item only once", async () => {
    vi.mocked(streamScreenerStrategy).mockReturnValue({
      promise: Promise.resolve({
        ...strategyResult,
        matches: [{
          code: "688836",
          signal_date: "2026-08-20",
          target_position: 1,
          signal_age_bars: 1,
          entry_price: 10,
          latest_price: 11,
          return_since_signal_pct: 10,
          average_amount_20d_yi: 2,
        }],
        matched_codes: ["688836"],
        evaluated: 1,
      }),
      started: Promise.resolve({ job: { id: "job" }, attached: false }),
      cancel: vi.fn(),
      detach: vi.fn(),
    });
    const { result } = renderHook(() => useRunScreenerStrategy(), { wrapper: createWrapper() });

    let executionResult;
    await act(async () => {
      executionResult = await result.current.mutateAsync({
        strategy_key: "bull_trend",
        codes: ["688836", "688836"],
        candidate_items: [
          { ...candidateStock, code: "688836", name: "N宇树" },
          { ...candidateStock, code: "688836", name: "N宇树" },
        ],
        scan_limit: 50,
      });
    });

    expect(executionResult).toEqual(expect.objectContaining({
      matched_items: [expect.objectContaining({ code: "688836", name: "N宇树" })],
    }));
  });
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(streamScreenerStrategy).mockReturnValue({
      promise: Promise.resolve(strategyResult),
      started: Promise.resolve({ job: { id: "job" }, attached: false }),
      cancel: vi.fn(),
      detach: vi.fn(),
    });
  });

  it("uses the current-page candidates for the 50-stock path", async () => {
    const onProgress = vi.fn();
    const { result } = renderHook(() => useRunScreenerStrategy(), { wrapper: createWrapper() });

    await act(async () => {
      await result.current.mutateAsync({
        strategy_key: "bull_trend",
        codes: ["600519", "000001"],
        scan_limit: 50,
        max_signal_age_bars: 30,
        onProgress,
      });
    });

    expect(apiPost).not.toHaveBeenCalled();
    expect(streamScreenerStrategy).toHaveBeenCalledWith(
      expect.objectContaining({
        codes: ["600519", "000001"],
        max_signal_age_bars: 30,
      }),
      onProgress,
    );
  });

  it("reloads the first 200 filtered candidates before starting the workflow", async () => {
    vi.mocked(apiPost).mockResolvedValue({
      items: [{ ...candidateStock, code: "600000", name: "浦发银行" }, candidateStock],
      total: 2,
      page: 1,
      page_size: 200,
    });
    const onProgress = vi.fn();
    const { result } = renderHook(() => useRunScreenerStrategy(), { wrapper: createWrapper() });

    await act(async () => {
      await result.current.mutateAsync({
        strategy_key: "bull_trend",
        codes: ["600519"],
        scan_limit: 200,
        candidate_filters: {
          page: 3,
          page_size: 50,
          sort_by: "market_cap",
          sort_order: "desc",
        },
        onProgress,
      });
    });

    expect(apiPost).toHaveBeenCalledWith(
      "/screener/screen",
      expect.objectContaining({ page: 1, page_size: 200 }),
      expect.objectContaining({
        signal: expect.any(AbortSignal),
        timeoutMs: 300_000,
      }),
    );
    expect(streamScreenerStrategy).toHaveBeenCalledWith(
      expect.objectContaining({ codes: ["600000", "000001"] }),
      onProgress,
    );
  });

  it("returns matched stock details from outside the visible current page", async () => {
    vi.mocked(apiPost).mockResolvedValue({
      items: [candidateStock],
      total: 1,
      page: 1,
      page_size: 200,
    });
    vi.mocked(streamScreenerStrategy).mockReturnValue({
      promise: Promise.resolve({
        ...strategyResult,
        matches: [{
          code: "000001",
          signal_date: "2026-08-16",
          target_position: 1,
          signal_age_bars: 2,
          entry_price: 10,
          latest_price: 12,
          return_since_signal_pct: 20,
          average_amount_20d_yi: 2,
        }],
        matched_codes: ["000001"],
        evaluated: 1,
      }),
      started: Promise.resolve({ job: { id: "job" }, attached: false }),
      cancel: vi.fn(),
      detach: vi.fn(),
    });
    const { result } = renderHook(() => useRunScreenerStrategy(), { wrapper: createWrapper() });

    let executionResult;
    await act(async () => {
      executionResult = await result.current.mutateAsync({
        strategy_key: "bull_trend",
        codes: ["600519"],
        scan_limit: 200,
        candidate_filters: { page: 1, page_size: 50, sort_by: "market_cap", sort_order: "desc" },
      });
    });

    expect(executionResult).toEqual(expect.objectContaining({
      matched_items: [candidateStock],
    }));
  });

  it("does not submit an invalid workflow when the 200-stock candidate set is empty", async () => {
    vi.mocked(apiPost).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 200 });
    const { result } = renderHook(() => useRunScreenerStrategy(), { wrapper: createWrapper() });

    await expect(result.current.mutateAsync({
      strategy_key: "bull_trend",
      codes: ["600519"],
      scan_limit: 200,
      candidate_filters: { page: 1, page_size: 50, sort_by: "market_cap", sort_order: "desc" },
    })).rejects.toThrow("没有可执行策略的候选股票");
    expect(streamScreenerStrategy).not.toHaveBeenCalled();
  });

  it("can cancel while the first 200 candidates are still loading", async () => {
    const candidates = deferred<{
      items: Array<{ code: string }>;
      total: number;
      page: number;
      page_size: number;
    }>();
    vi.mocked(apiPost).mockReturnValue(candidates.promise);
    const onStarted = vi.fn();
    const { result } = renderHook(() => useRunScreenerStrategy(), { wrapper: createWrapper() });

    let execution!: Promise<ScreenerStrategyResult>;
    await act(async () => {
      execution = result.current.mutateAsync({
        strategy_key: "bull_trend",
        codes: ["600519"],
        scan_limit: 200,
        candidate_filters: { page: 1, page_size: 50, sort_by: "market_cap", sort_order: "desc" },
        onStarted,
      });
      await Promise.resolve();
    });
    await vi.waitFor(() => expect(onStarted).toHaveBeenCalledTimes(1));
    const cancel = onStarted.mock.calls[0][0] as () => void;
    await act(async () => {
      cancel();
      candidates.resolve({ items: [{ code: "600000" }], total: 1, page: 1, page_size: 200 });
      await expect(execution).rejects.toThrow("已取消");
    });
    expect(streamScreenerStrategy).not.toHaveBeenCalled();
  });
});
