import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { QUERY_CACHE_POLICIES } from "../cachePolicies";
import { API_TIMEOUTS } from "../client";
import { openApiGet, type OpenApiResponse } from "../openapiClient";
import { queryKeys } from "../queryKeys";
import { useHKStockTradingSession } from "../../hooks/useHKStockTradingSession";
import { usePageVisibility } from "../../hooks/usePageVisibility";

export type HKStockQuotePage = OpenApiResponse<"/api/hk/stocks/realtime", "get">;
export type HKStockQuote = HKStockQuotePage["items"][number];
export type HKStockSearchResult = OpenApiResponse<"/api/hk/stocks/search", "get">;
export type HKStockSearchItem = HKStockSearchResult["items"][number];
export type HKIndices = OpenApiResponse<"/api/hk/indices/realtime", "get">;
export type HKKlineData = OpenApiResponse<"/api/hk/indices/{symbol}/history", "get">;

export function useHKIndices() {
  const isTradingSession = useHKStockTradingSession();
  const isVisible = usePageVisibility();
  return useQuery({
    queryKey: queryKeys.hk.indices,
    queryFn: () => openApiGet("/api/hk/indices/realtime", {
      query: {},
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    refetchInterval: isTradingSession && isVisible ? 30_000 : false,
  });
}

export function useHKIndexHistory(symbol: string, period: string) {
  return useQuery({
    queryKey: queryKeys.hk.indexHistory(symbol, period),
    queryFn: () => openApiGet("/api/hk/indices/{symbol}/history", {
      path: { symbol },
      query: { period, start_date: "", end_date: "" },
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    enabled: Boolean(symbol),
    placeholderData: (previous) => previous,
  });
}

export function useHKStocks(query: string, page: number, pageSize: number) {
  const isTradingSession = useHKStockTradingSession();
  const isVisible = usePageVisibility();
  return useQuery({
    queryKey: queryKeys.hk.stocks(query, page, pageSize),
    queryFn: () => openApiGet("/api/hk/stocks/realtime", {
      query: { query, codes: "", page, page_size: pageSize },
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    placeholderData: keepPreviousData,
    refetchInterval: isTradingSession && isVisible ? 30_000 : false,
  });
}

export function useHKStockSearch(query: string) {
  return useQuery({
    queryKey: queryKeys.hk.stockSearch(query),
    queryFn: ({ signal }) => openApiGet("/api/hk/stocks/search", {
      query: { q: query, limit: 8 },
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL, signal },
    }),
    enabled: Boolean(query),
    staleTime: QUERY_CACHE_POLICIES.hkStockSearch.staleMs,
    gcTime: QUERY_CACHE_POLICIES.hkStockSearch.gcMs,
  });
}

export function useHKStockHistory(code: string, period: string, adjust: string, startDate = "") {
  const adjustParam = adjust || "none";
  return useQuery({
    queryKey: queryKeys.hk.stockHistory(code, period, adjustParam, startDate),
    queryFn: () => openApiGet("/api/hk/stocks/{code}/history", {
      path: { code },
      query: { period, adjust: adjustParam, start_date: startDate || "", end_date: "" },
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    enabled: Boolean(code),
    placeholderData: (previous) => previous,
  });
}

export function useHKStockQuote(code: string) {
  const isTradingSession = useHKStockTradingSession();
  const isVisible = usePageVisibility();
  return useQuery({
    queryKey: queryKeys.hk.stockQuote(code),
    queryFn: async () => {
      const page = await openApiGet("/api/hk/stocks/realtime", {
        query: { codes: code, query: "", page: 1, page_size: 1 },
        options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
      });
      return page.items[0] ?? null;
    },
    enabled: Boolean(code),
    refetchInterval: isTradingSession && isVisible ? 30_000 : false,
  });
}
