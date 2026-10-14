import { StrictMode, type PropsWithChildren } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  useAnalysisPageData,
  useAnalysisSnapshot,
  useStockInfo,
  useStockFundFlow,
  useStockFundFlowPages,
  useDeleteAnalysisHistory,
  useDeleteDailyReview,
  useDeleteIndustryChainArchive,
  useInfiniteIndustryChainHistory,
  useKlineData,
  useGenerateQuantStrategyDraft,
  usePublishQuantStrategyDraft,
  useScreenerScreen,
  useUpdateQuantStrategyDraft,
  useValuationDetail,
  type QuantStrategyDraft,
  type QuantStrategyDefinitionInput,
} from "./queries";
import { API_TIMEOUTS, apiDelete, apiGet, apiPost, apiPut } from "./client";
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

    const { result } = renderHook(() => useStockInfo("600519"), { wrapper });

    await waitFor(() => expect(apiGet).toHaveBeenCalledTimes(1));

    await act(async () => resolveRequest?.({ code: "600519" }));

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    client.clear();
  });

  it("allows the slower fund-flow fallback to finish without the default 15s cutoff", async () => {
    vi.mocked(apiGet).mockResolvedValue([]);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    const { result, unmount } = renderHook(() => useStockFundFlow("600519"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiGet).toHaveBeenCalledWith("/stock/600519/fund-flow", undefined, { timeoutMs: 120000 });
    unmount();
    client.clear();
  });

  it("fetches funding batches on demand and retries a failed cursor without losing loaded pages", async () => {
    const first = { items: [{ date: "2026-09-24" }], total: 60, next_cursor: "session:20", source: "tdxhub", source_api: "tdxhub.capital_flow" };
    const second = { ...first, items: [{ date: "2026-08-24" }], next_cursor: "session:40" };
    vi.mocked(apiGet).mockResolvedValueOnce(first).mockRejectedValueOnce(new Error("batch failed")).mockResolvedValueOnce(second);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
    const { result, rerender, unmount } = renderHook(({ code }) => useStockFundFlowPages(code), { wrapper, initialProps: { code: "600519" } });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiGet).toHaveBeenCalledTimes(1);
    expect(result.current.data?.pages).toEqual([first]);
    expect(result.current.hasNextPage).toBe(true);
    await act(async () => { await result.current.fetchNextPage(); });
    await waitFor(() => expect(result.current.isFetchNextPageError).toBe(true));
    expect(result.current.data?.pages).toEqual([first]);
    await act(async () => { await result.current.fetchNextPage(); });
    await waitFor(() => expect(result.current.isFetchNextPageError).toBe(false));
    expect(result.current.data?.pages).toEqual([first, second]);
    expect(apiGet).toHaveBeenNthCalledWith(2, "/stock/600519/fund-flow-pages", { cursor: "session:20" }, { timeoutMs: 120000 });
    expect(apiGet).toHaveBeenNthCalledWith(3, "/stock/600519/fund-flow-pages", { cursor: "session:20" }, { timeoutMs: 120000 });
    vi.mocked(apiGet).mockResolvedValueOnce({ ...first, items: [], total: 0, next_cursor: null });
    rerender({ code: "000001" });
    expect(result.current.data).toBeUndefined();
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.hasNextPage).toBe(false);
    unmount();
    client.clear();
  });

  it("loads only the cached research snapshot for profile fundamentals", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    vi.mocked(apiGet).mockResolvedValue({ cached_analysis: { fundamental: { summary: "盈利稳健" } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    const { result, unmount } = renderHook(() => useAnalysisSnapshot("600519"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.cached_analysis?.fundamental.summary).toBe("盈利稳健");
    expect(apiGet).toHaveBeenCalledTimes(1);
    expect(apiGet).toHaveBeenCalledWith("/stock/analysis-page/600519", { include_market_data: false }, undefined);
    unmount();
    client.clear();
  });

  it("reuses stock profile caches and only fetches the research snapshot", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const stockInfo = { code: "600519", name: "贵州茅台", current_price: 1520, pe_ttm: 23.1, pb: 7.8 };
    const intraday = { code: "600519", prev_close: 1500, items: [{ price: 1535 }] };
    client.setQueryData(queryKeys.stock.info("600519"), stockInfo);
    client.setQueryData(queryKeys.stock.intraday("600519"), intraday);
    vi.mocked(apiGet).mockResolvedValue({ cached_analysis: null });
    const wrapper = ({ children }: PropsWithChildren) => (
      <StrictMode><QueryClientProvider client={client}>{children}</QueryClientProvider></StrictMode>
    );
    const { result, unmount } = renderHook(() => useAnalysisPageData("600519"), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(apiGet).toHaveBeenCalledTimes(1);
    expect(apiGet).toHaveBeenCalledWith("/stock/analysis-page/600519", { include_market_data: false }, undefined);
    expect(result.current.data?.stock_info).toBe(stockInfo);
    expect(result.current.data?.intraday).toBe(intraday);
    expect(result.current.data?.valuation).toMatchObject({ pe_ttm: 23.1, pb: 7.8 });
    expect(result.current.data?.kline).toBeNull();
    await act(async () => {
      client.setQueryData(queryKeys.stock.analysisPage("600519"), { cached_analysis: { overall_rating: 8 } });
    });
    await waitFor(() => expect(result.current.data?.cached_analysis?.overall_rating).toBe(8));
    unmount();
    client.clear();
  });

  it("loads shared resources once on direct analysis navigation and isolates stock codes", async () => {
    vi.mocked(apiGet).mockImplementation(async (path) => {
      if (path.includes("analysis-page")) return { cached_analysis: null };
      if (path.endsWith("/intraday")) return { items: [], prev_close: 10 };
      return { code: path.split("/")[2], current_price: 10 };
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <StrictMode><QueryClientProvider client={client}>{children}</QueryClientProvider></StrictMode>
    );
    const { result, rerender, unmount } = renderHook(
      ({ code }) => useAnalysisPageData(code), { initialProps: { code: "600519" }, wrapper },
    );
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(apiGet).toHaveBeenCalledTimes(3);
    expect(vi.mocked(apiGet).mock.calls.map(([path]) => path).sort()).toEqual([
      "/stock/600519/info", "/stock/600519/intraday", "/stock/analysis-page/600519",
    ]);
    rerender({ code: "000001" });
    await waitFor(() => expect(result.current.data?.stock_info?.code).toBe("000001"));
    expect(apiGet).toHaveBeenCalledTimes(6);
    unmount();
    client.clear();
  });

  it.each([{ code: "600519", enabled: false }, { code: "", enabled: true }])(
    "does not fetch disabled analysis resources: %s", ({ code, enabled }) => {
      const client = new QueryClient();
      const wrapper = ({ children }: PropsWithChildren) => (
        <QueryClientProvider client={client}>{children}</QueryClientProvider>
      );
      const { unmount } = renderHook(() => useAnalysisPageData(code, { enabled }), { wrapper });
      expect(apiGet).not.toHaveBeenCalled();
      unmount();
      client.clear();
    },
  );

  it("keeps the research result available when shared market data fails", async () => {
    vi.mocked(apiGet).mockImplementation(async (path) => {
      if (path.includes("analysis-page")) return { cached_analysis: { overall_rating: 7.5 } };
      throw new Error("market unavailable");
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    const { result, unmount } = renderHook(() => useAnalysisPageData("600519"), { wrapper });
    await waitFor(() => expect(result.current.data?.unavailable_sections).toEqual(["stock_info", "intraday"]));
    expect(result.current.data?.cached_analysis?.overall_rating).toBe(7.5);
    expect(result.current.data?.partial).toBe(true);
    unmount();
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
      { timeoutMs: API_TIMEOUTS.EXTERNAL },
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

  it("requests valuation detail with external timeout budget", async () => {
    vi.mocked(apiGet).mockResolvedValue({ code: "600519" });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useValuationDetail("600519"), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(apiGet).toHaveBeenCalledWith(
      "/stock/600519/valuation-detail",
      undefined,
      { timeoutMs: API_TIMEOUTS.EXTERNAL },
    );
    client.clear();
  });
});

