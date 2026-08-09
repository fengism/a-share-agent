import type { PropsWithChildren } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  useAnalysisPageData,
  useDeleteAnalysisHistory,
  useDeleteDailyReview,
  useDeleteIndustryChainArchive,
  useInfiniteIndustryChainHistory,
  useKlineData,
  useScreenerScreen,
} from "./queries";
import { apiDelete, apiGet, apiPost } from "./client";
import type { ScreenerFilter, ScreenerResult } from "../types/stock";

vi.mock("./client", async () => {
  const actual = await vi.importActual<typeof import("./client")>("./client");
  return { ...actual, apiDelete: vi.fn(), apiGet: vi.fn(), apiPost: vi.fn() };
});

describe("query request cancellation", () => {
  afterEach(() => {
    vi.mocked(apiDelete).mockReset();
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
  });

  it("passes TanStack's abort signal into the API client", async () => {
    let requestSignal: AbortSignal | undefined;
    vi.mocked(apiGet).mockImplementation((_path, _params, options) => {
      requestSignal = options?.signal;
      return new Promise(() => undefined);
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );

    const { unmount } = renderHook(() => useAnalysisPageData("600519"), { wrapper });
    await waitFor(() => expect(requestSignal).toBeDefined());

    unmount();

    expect(requestSignal?.aborted).toBe(true);
    client.clear();
  });

  it("keeps the aggregate K-line request disabled until a non-default view is selected", async () => {
    vi.mocked(apiGet).mockResolvedValue({ code: "600519", period: "weekly", items: [] });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );

    const { rerender } = renderHook(
      ({ enabled }) => useKlineData("600519", "weekly", "hfq", enabled),
      { initialProps: { enabled: false }, wrapper },
    );

    expect(apiGet).not.toHaveBeenCalled();

    rerender({ enabled: true });
    await waitFor(() => expect(apiGet).toHaveBeenCalledTimes(1));
    expect(apiGet).toHaveBeenCalledWith(
      "/stock/600519/kline",
      expect.objectContaining({ period: "weekly", adjust: "hfq" }),
      { signal: expect.any(AbortSignal) },
    );
    client.clear();
  });

  it("advances history offsets and stops after a short page", async () => {
    vi.mocked(apiGet)
      .mockResolvedValueOnce([
        { name: "AI", archive_id: "3", saved_at: "", title: "", summary: "", can_delete: true },
        { name: "AI", archive_id: "2", saved_at: "", title: "", summary: "", can_delete: true },
      ])
      .mockResolvedValueOnce([
        { name: "AI", archive_id: "1", saved_at: "", title: "", summary: "", can_delete: true },
      ]);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useInfiniteIndustryChainHistory("AI", 2), { wrapper });
    await waitFor(() => expect(result.current.data?.pages).toHaveLength(1));
    expect(apiGet).toHaveBeenNthCalledWith(
      1,
      "/industry-chain/history",
      { name: "AI", limit: 2, offset: 0 },
      { signal: expect.any(AbortSignal) },
    );

    await act(async () => {
      await result.current.fetchNextPage();
    });

    expect(apiGet).toHaveBeenNthCalledWith(
      2,
      "/industry-chain/history",
      { name: "AI", limit: 2, offset: 2 },
      { signal: expect.any(AbortSignal) },
    );
    await waitFor(() => expect(result.current.data?.pages).toHaveLength(2));
    expect(result.current.data?.pages.flat()).toHaveLength(3);
    expect(result.current.hasNextPage).toBe(false);
    client.clear();
  });

  it("uses the expected DELETE endpoint for each history type", async () => {
    vi.mocked(apiDelete).mockResolvedValue({ deleted: true });
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    const analysis = renderHook(() => useDeleteAnalysisHistory(), { wrapper });
    const industry = renderHook(() => useDeleteIndustryChainArchive(), { wrapper });
    const dailyReview = renderHook(() => useDeleteDailyReview(), { wrapper });

    await act(async () => {
      await analysis.result.current.mutateAsync({ code: "600519", date: "20260807" });
      await industry.result.current.mutateAsync({ name: "AI 芯片", archiveId: "20260807_120000" });
      await dailyReview.result.current.mutateAsync("2026-08-07");
    });

    expect(apiDelete).toHaveBeenNthCalledWith(1, "/analysis/600519/history/20260807");
    expect(apiDelete).toHaveBeenNthCalledWith(
      2,
      "/industry-chain/AI%20%E8%8A%AF%E7%89%87/archive/20260807_120000",
    );
    expect(apiDelete).toHaveBeenNthCalledWith(3, "/daily-review/2026-08-07");
    client.clear();
  });

  it("keeps the previous screener result while a new filter request is pending", async () => {
    const firstResult = {
      items: [{ code: "600519", name: "贵州茅台" }],
      total: 1,
      page: 1,
      page_size: 20,
    } as ScreenerResult;
    let resolveSecond: ((value: ScreenerResult) => void) | undefined;
    vi.mocked(apiPost)
      .mockResolvedValueOnce(firstResult)
      .mockImplementationOnce(() => new Promise((resolve) => {
        resolveSecond = resolve as (value: ScreenerResult) => void;
      }));
    const firstFilters = {
      page: 1,
      page_size: 20,
      sort_by: "market_cap",
      sort_order: "desc",
    } as ScreenerFilter;
    const secondFilters = { ...firstFilters, page: 2 };
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );

    const { result, rerender } = renderHook(
      ({ filters }) => useScreenerScreen(filters),
      { initialProps: { filters: firstFilters }, wrapper },
    );
    await waitFor(() => expect(result.current.data).toEqual(firstResult));

    rerender({ filters: secondFilters });

    await waitFor(() => expect(result.current.isFetching).toBe(true));
    expect(result.current.data).toEqual(firstResult);

    resolveSecond?.({ ...firstResult, page: 2 });
    await waitFor(() => expect(result.current.data?.page).toBe(2));
    client.clear();
  });
});
