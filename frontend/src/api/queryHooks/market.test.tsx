import type { PropsWithChildren } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiGet, apiPost, API_TIMEOUTS } from "../client";
import { queryKeys } from "../queryKeys";
import {
  useForceRefreshMacroAllData,
  useMarketTwitterAnalysisRefresh,
  useMarketTwitterFeedRefresh,
} from "./market";
import type { MacroAllData } from "../../types/stock";

vi.mock("../client", async () => {
  const actual = await vi.importActual<typeof import("../client")>("../client");
  return { ...actual, apiGet: vi.fn(), apiPost: vi.fn() };
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
