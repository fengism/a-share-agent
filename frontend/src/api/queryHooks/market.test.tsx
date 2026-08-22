import type { PropsWithChildren } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import dayjs from "dayjs";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet, apiPost, API_TIMEOUTS } from "../client";
import { queryKeys } from "../queryKeys";
import {
  useForceRefreshMacroAllData,
  useIndustryRankings,
  useMarketIndices,
  useMarketIndexIntraday,
  useMarketEmotion,
  useMarketLimitHistory,
  useMarketMainline,
  useMarketSectorStocksHistory,
  useMarketLimitUpLadder,
  useMarketWind,
  useMarketWindStocks,
  useThsHotRank,
  useThsHotConcept,
  useThsHotIndustry,
  useMarketTwitterAnalysisRefresh,
  useMarketTwitterFeedRefresh,
} from "./market";
import type { MacroAllData } from "../../types/stock";

const mocks = vi.hoisted(() => ({
  isTradingSession: true,
}));

vi.mock("../client", async () => {
  const actual = await vi.importActual<typeof import("../client")>("../client");
  return { ...actual, apiGet: vi.fn(), apiPost: vi.fn() };
});

vi.mock("../../hooks/useAStockTradingSession", () => ({
  useAStockTradingSession: () => mocks.isTradingSession,
}));

describe("market emotion query", () => {
  beforeEach(() => {
    mocks.isTradingSession = true;
  });

  afterEach(() => vi.mocked(apiGet).mockReset());

  it("refreshes index intraday data every thirty seconds during trading", async () => {
    vi.mocked(apiGet).mockResolvedValue({ code: "000001", source: "sina_direct", prev_close: null, items: [] });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useMarketIndexIntraday("000001"), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiGet).toHaveBeenCalledWith(
      "/market/index-intraday",
      { symbol: "000001" },
      { timeoutMs: API_TIMEOUTS.EXTERNAL },
    );
    const options = queryClient.getQueryCache().find({
      queryKey: queryKeys.market.indexIntraday("000001"),
    })?.options as { refetchInterval?: unknown; staleTime?: unknown } | undefined;
    expect(options?.refetchInterval).toBe(30_000);
    expect(options?.staleTime).toBe(30_000);
    queryClient.clear();
  });

  it("keeps realtime indices warm and refreshes stale data on window focus", async () => {
    vi.mocked(apiGet).mockResolvedValue({ source: "腾讯", indices: [] });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useMarketIndices(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const options = queryClient.getQueryCache().find({ queryKey: queryKeys.market.indices })?.options as {
      refetchOnWindowFocus?: unknown;
      staleTime?: unknown;
      refetchInterval?: unknown;
    } | undefined;
    expect(options?.refetchOnWindowFocus).toBe(true);
    expect(options?.staleTime).toBe(30_000);
    expect(options?.refetchInterval).toBe(30_000);
    queryClient.clear();
  });

  it("requests CLS emotion data and refreshes it every sixty seconds", async () => {
    vi.mocked(apiGet).mockResolvedValue({
      source: "财联社",
      fetched_at: "2026-08-13T10:30:00+08:00",
      market_degree: 37,
      shsz_balance: "1.77万亿",
      shsz_balance_change_px: "+1932亿",
      preview_balance: "2.4万亿",
      preview_balance_change_px: "+2478亿",
      up_ratio: "77.00%",
      up_ratio_num: 67,
      up_open_num: 19,
      performance: "1.72%",
      up_open_ratio: "57%",
      profit_ratio: "53%",
      up_down_dis: { rise_num: 2194, fall_num: 3202 },
      limit_up_board: [],
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useMarketEmotion(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiGet).toHaveBeenCalledWith(
      "/market/emotion",
      undefined,
      { timeoutMs: API_TIMEOUTS.EXTERNAL },
    );
    const queryOptions = queryClient.getQueryCache().find({ queryKey: queryKeys.market.emotion })?.options as {
      refetchInterval?: unknown;
    } | undefined;
    expect(queryOptions?.refetchInterval).toBe(60_000);
    queryClient.clear();
  });


  it("refreshes THS hot ranks every five minutes", async () => {
    vi.mocked(apiGet).mockResolvedValue([]);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => ({
      stocks: useThsHotRank(),
      concepts: useThsHotConcept(),
      industries: useThsHotIndustry(),
    }), { wrapper });

    await waitFor(() => expect(
      result.current.stocks.isSuccess
      && result.current.concepts.isSuccess
      && result.current.industries.isSuccess,
    ).toBe(true));
    for (const queryKey of [
      queryKeys.market.thsHotRank,
      queryKeys.market.thsHotConcept,
      queryKeys.market.thsHotIndustry,
    ]) {
      const options = queryClient.getQueryCache().find({ queryKey })?.options as {
        staleTime?: unknown;
        refetchInterval?: unknown;
      } | undefined;
      expect(options?.staleTime).toBe(5 * 60_000);
      expect(options?.refetchInterval).toBe(5 * 60_000);
    }
    queryClient.clear();
  });

  it("refreshes current Kaipanhong industry rankings every sixty seconds", async () => {
    const today = dayjs().format("YYYY-MM-DD");
    vi.mocked(apiGet).mockResolvedValue({
      source: "开盘红",
      date: today,
      fund_data_available: true,
      total: 0,
      sectors: [],
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useIndustryRankings(today), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiGet).toHaveBeenCalledWith(
      "/market/industry-rankings",
      { date: today },
      { timeoutMs: API_TIMEOUTS.EXTERNAL },
    );
    const queryOptions = queryClient.getQueryCache().find({
      queryKey: queryKeys.market.industryRankings(today),
    })?.options as {
      staleTime?: unknown;
      refetchInterval?: unknown;
    } | undefined;
    expect(queryOptions?.staleTime).toBe(60_000);
    expect(queryOptions?.refetchInterval).toBe(60_000);
    queryClient.clear();
  });

  it("keeps historical industry rankings for twenty-four hours without polling", async () => {
    vi.mocked(apiGet).mockResolvedValue({
      source: "开盘红",
      date: "2026-08-20",
      fund_data_available: true,
      total: 0,
      sectors: [],
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useIndustryRankings("2026-08-20"), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const queryOptions = queryClient.getQueryCache().find({
      queryKey: queryKeys.market.industryRankings("2026-08-20"),
    })?.options as {
      staleTime?: unknown;
      refetchInterval?: unknown;
    } | undefined;
    expect(queryOptions?.staleTime).toBe(86_400_000);
    expect(queryOptions?.refetchInterval).toBe(false);
    queryClient.clear();
  });

  it("requests wind plates and stocks with sixty-second refresh", async () => {
    vi.mocked(apiGet).mockImplementation(async (path) => (
      path === "/market/today-wind"
        ? { source: "财联社", fetched_at: "2026-08-13T10:30:00+08:00", items: [] }
        : { source: "财联社", fetched_at: "2026-08-13T10:30:00+08:00", plate_code: "cls80044", items: [] }
    ));
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => ({
      wind: useMarketWind(),
      stocks: useMarketWindStocks("cls80044"),
    }), { wrapper });

    await waitFor(() => expect(result.current.wind.isSuccess && result.current.stocks.isSuccess).toBe(true));
    expect(apiGet).toHaveBeenCalledWith(
      "/market/today-wind",
      undefined,
      { timeoutMs: API_TIMEOUTS.EXTERNAL },
    );
    expect(apiGet).toHaveBeenCalledWith(
      "/market/today-wind/cls80044/stocks",
      undefined,
      { timeoutMs: API_TIMEOUTS.EXTERNAL },
    );
    for (const queryKey of [queryKeys.market.wind, queryKeys.market.windStocks("cls80044")]) {
      const options = queryClient.getQueryCache().find({ queryKey })?.options as {
        refetchInterval?: unknown;
      } | undefined;
      expect(options?.refetchInterval).toBe(60_000);
    }
    queryClient.clear();
  });

  it("requests CLS mainline chances with sixty-second refresh", async () => {
    vi.mocked(apiGet).mockResolvedValue({
      source: "财联社",
      fetched_at: "2026-08-21T10:30:00+08:00",
      items: [],
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useMarketMainline(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiGet).toHaveBeenCalledWith(
      "/market/mainline",
      undefined,
      { timeoutMs: API_TIMEOUTS.EXTERNAL },
    );
    const options = queryClient.getQueryCache().find({
      queryKey: queryKeys.market.mainline,
    })?.options as { refetchInterval?: unknown; staleTime?: unknown } | undefined;
    expect(options?.refetchInterval).toBe(60_000);
    expect(options?.staleTime).toBe(60_000);
    queryClient.clear();
  });

  it("requests the Kaipanhong limit-up ladder with sixty-second refresh", async () => {
    vi.mocked(apiGet).mockResolvedValue({
      source: "开盘红",
      date: "2026-08-12",
      fetched_at: "2026-08-13T10:30:00+08:00",
      total: 0,
      stocks: [],
      sectors: [],
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useMarketLimitUpLadder("2026-08-13"), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiGet).toHaveBeenCalledWith(
      "/market/limit-up-ladder",
      { date: "2026-08-13" },
      { timeoutMs: API_TIMEOUTS.EXTERNAL },
    );
    const options = queryClient.getQueryCache().find({
      queryKey: queryKeys.market.limitUpLadder("2026-08-13"),
    })?.options as { refetchInterval?: unknown } | undefined;
    expect(options?.refetchInterval).toBe(60_000);
    queryClient.clear();
  });

  it("requests Kaipanhong limit history without interval refresh", async () => {
    vi.mocked(apiGet).mockResolvedValue({
      source: "开盘红",
      date: "2026-08-20",
      category: "limit_down",
      fetched_at: "2026-08-21T08:00:00+00:00",
      total: 0,
      items: [],
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(
      () => useMarketLimitHistory("2026-08-20", "limit_down"),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiGet).toHaveBeenCalledWith(
      "/market/limit-history",
      { date: "2026-08-20", category: "limit_down" },
      { timeoutMs: API_TIMEOUTS.EXTERNAL },
    );
    const options = queryClient.getQueryCache().find({
      queryKey: queryKeys.market.limitHistory("2026-08-20", "limit_down"),
    })?.options as { refetchInterval?: unknown; staleTime?: unknown } | undefined;
    expect(options?.refetchInterval).toBeUndefined();
    expect(options?.staleTime).toBe(86_400_000);
    queryClient.clear();
  });

  it("requests Kaipanhong sector stocks history without interval refresh", async () => {
    vi.mocked(apiGet).mockResolvedValue({
      source: "开盘红",
      date: "2026-08-20",
      plate_id: "881169",
      fetched_at: "2026-08-21T08:00:00+00:00",
      total: 0,
      items: [],
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(
      () => useMarketSectorStocksHistory("2026-08-20", "881169"),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiGet).toHaveBeenCalledWith(
      "/market/sector-stocks-history",
      { date: "2026-08-20", plate_id: "881169" },
      { timeoutMs: API_TIMEOUTS.EXTERNAL },
    );
    const options = queryClient.getQueryCache().find({
      queryKey: queryKeys.market.sectorStocksHistory("2026-08-20", "881169"),
    })?.options as { refetchInterval?: unknown; staleTime?: unknown } | undefined;
    expect(options?.refetchInterval).toBeUndefined();
    expect(options?.staleTime).toBe(86_400_000);
    queryClient.clear();
  });

  it("keeps the initial request but disables interval refresh outside trading sessions", async () => {
    mocks.isTradingSession = false;
    vi.mocked(apiGet).mockResolvedValue({
      source: "财联社",
      fetched_at: "2026-08-14T16:00:00+08:00",
      market_degree: 37,
      limit_up_board: [],
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(() => useMarketEmotion(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(apiGet).toHaveBeenCalledTimes(1);
    const options = queryClient.getQueryCache().find({ queryKey: queryKeys.market.emotion })?.options as {
      refetchInterval?: unknown;
    } | undefined;
    expect(options?.refetchInterval).toBe(false);
    queryClient.clear();
  });
});

describe("macro data queries", () => {
  afterEach(() => {
    vi.mocked(apiGet).mockReset();
    vi.mocked(apiPost).mockReset();
  });

  it("forces a server refresh and replaces the shared query cache", async () => {
    const freshData: MacroAllData = {
      prices: {},
      sentiment: {},
      monetary: {},
      rates: {},
      growth: {},
      trade: {},
    };
    vi.mocked(apiGet).mockResolvedValue(freshData);
    const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => useForceRefreshMacroAllData(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync();
    });

    expect(apiGet).toHaveBeenCalledWith(
      "/macro/all",
      { force_refresh: true },
      { timeoutMs: API_TIMEOUTS.EXTERNAL },
    );
    expect(queryClient.getQueryData(["macroAllData"])).toEqual(freshData);
    queryClient.clear();
  });
});

describe("twitter data queries", () => {
  afterEach(() => vi.mocked(apiPost).mockReset());

  it("invalidates the feed and all account analyses after a manual refresh", async () => {
    vi.mocked(apiPost).mockResolvedValue({ status: "ok" });
    const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const invalidateQueries = vi.spyOn(queryClient, "invalidateQueries").mockResolvedValue();
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => useMarketTwitterFeedRefresh(), { wrapper });

    await act(async () => {
      await result.current.mutateAsync();
    });

    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queryKeys.market.twitterFeed });
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: queryKeys.market.twitterAnalysisRoot });
    queryClient.clear();
  });

  it("forces regeneration and replaces the normal account analysis cache", async () => {
    const regenerated = {
      username: "market-author",
      article_count: 1,
      articles: [],
      analysis: "重新生成",
    };
    vi.mocked(apiGet).mockResolvedValue(regenerated);
    const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const { result } = renderHook(() => useMarketTwitterAnalysisRefresh("market-author"), { wrapper });

    await act(async () => {
      await result.current.mutateAsync();
    });

    expect(apiGet).toHaveBeenCalledWith(
      "/market/twitter-analyze",
      { username: "market-author", force_refresh: true },
      { timeoutMs: API_TIMEOUTS.LONG_RUNNING },
    );
    expect(queryClient.getQueryData(queryKeys.market.twitterAnalysis("market-author"))).toEqual(regenerated);
    queryClient.clear();
  });
});
