import { StrictMode, type PropsWithChildren } from "react";
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
  useGenerateQuantStrategyDraft,
  usePublishQuantStrategyDraft,
  useScreenerScreen,
  useUpdateQuantStrategyDraft,
  type QuantStrategyDraft,
  type QuantStrategyDefinitionInput,
} from "./queries";
import { apiDelete, apiGet, apiPost, apiPut } from "./client";
import { queryKeys } from "./queryKeys";
import type { ScreenerFilter, ScreenerResult } from "../types/stock";

vi.mock("./client", async () => {
  const actual = await vi.importActual<typeof import("./client")>("./client");
  return { ...actual, apiDelete: vi.fn(), apiGet: vi.fn(), apiPost: vi.fn(), apiPut: vi.fn() };
});

describe("query request lifecycle", () => {
  afterEach(() => {
    vi.mocked(apiDelete).mockReset();
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
    vi.mocked(apiPut).mockReset();
  });

  it("reuses an in-flight cacheable request across StrictMode remounts", async () => {
    let resolveRequest: ((value: unknown) => void) | undefined;
    vi.mocked(apiGet).mockImplementation(() => {
      return new Promise((resolve) => {
        resolveRequest = resolve;
      });
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <StrictMode>
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      </StrictMode>
    );

    const { result } = renderHook(() => useAnalysisPageData("600519"), { wrapper });

    await waitFor(() => expect(apiGet).toHaveBeenCalledTimes(1));

    await act(async () => resolveRequest?.({ code: "600519" }));

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
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
      undefined,
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
      { signal: expect.anything() },
    );

    await act(async () => {
      await result.current.fetchNextPage();
    });

    expect(apiGet).toHaveBeenNthCalledWith(
      2,
      "/industry-chain/history",
      { name: "AI", limit: 2, offset: 2 },
      { signal: expect.anything() },
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

  it("sends the current definition hash when updating a strategy draft", async () => {
    const original = { id: "draft-one", status: "validated" } as QuantStrategyDraft;
    const updated = { id: "draft-one", status: "draft" } as QuantStrategyDraft;
    vi.mocked(apiPut).mockResolvedValue(updated);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    client.setQueryData(queryKeys.quant.drafts, [original]);
    const cancel = vi.spyOn(client, "cancelQueries");
    const invalidate = vi.spyOn(client, "invalidateQueries");
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    const updateDraft = renderHook(() => useUpdateQuantStrategyDraft(), { wrapper });
    const definition = {} as QuantStrategyDefinitionInput;

    await act(async () => {
      await updateDraft.result.current.mutateAsync({
        draftId: "draft-one",
        expectedDefinitionHash: `sha256:${"a".repeat(64)}`,
        definition,
      });
    });

    expect(apiPut).toHaveBeenCalledWith(
      "/quant/strategy-drafts/draft-one",
      {
        definition,
        expected_definition_hash: `sha256:${"a".repeat(64)}`,
      },
    );
    expect(client.getQueryData(queryKeys.quant.drafts)).toEqual([updated]);
    expect(cancel).toHaveBeenCalledWith({ queryKey: queryKeys.quant.drafts });
    expect(invalidate).not.toHaveBeenCalled();
    client.clear();
  });

  it("prepends a generated strategy draft without refetching the list", async () => {
    const existing = { id: "draft-existing", status: "validated" } as QuantStrategyDraft;
    const generated = { id: "draft-generated", status: "validated" } as QuantStrategyDraft;
    vi.mocked(apiPost).mockResolvedValue(generated);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    client.setQueryData(queryKeys.quant.drafts, [existing]);
    const invalidate = vi.spyOn(client, "invalidateQueries");
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    const generateDraft = renderHook(() => useGenerateQuantStrategyDraft(), { wrapper });

    await act(async () => {
      await generateDraft.result.current.mutateAsync("生成一个二十日均线趋势策略");
    });

    expect(client.getQueryData(queryKeys.quant.drafts)).toEqual([generated, existing]);
    expect(invalidate).not.toHaveBeenCalled();
    client.clear();
  });

  it("updates the published draft cache and refreshes only registry dependencies", async () => {
    const backtested = { id: "draft-one", status: "backtested" } as QuantStrategyDraft;
    const published = { id: "draft-one", status: "published" } as QuantStrategyDraft;
    vi.mocked(apiPost).mockResolvedValue(published);
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    client.setQueryData(queryKeys.quant.drafts, [backtested]);
    const invalidate = vi.spyOn(client, "invalidateQueries");
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    const publishDraft = renderHook(() => usePublishQuantStrategyDraft(), { wrapper });

    await act(async () => {
      await publishDraft.result.current.mutateAsync({
        draftId: "draft-one",
        expectedDefinitionHash: `sha256:${"a".repeat(64)}`,
      });
    });

    expect(client.getQueryData(queryKeys.quant.drafts)).toEqual([published]);
    expect(invalidate).toHaveBeenCalledTimes(2);
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.quant.registry });
    expect(invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.quant.presets });
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
