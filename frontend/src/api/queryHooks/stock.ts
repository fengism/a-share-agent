import { useQuery } from "@tanstack/react-query";
import { QUERY_CACHE_POLICIES } from "../cachePolicies";
import { asApiModel, openApiGet } from "../openapiClient";
import { queryKeys } from "../queryKeys";
import { oneYearAgoDate } from "../../utils/date";
import { useAStockTradingSession } from "../../hooks/useAStockTradingSession";
import type {
  AnalysisPageData,
  CategorizedStockNews,
  IntradayData,
  KlineData,
  RetailSentiment,
  StockCompareItem,
  StockFundFlowItem,
  StockSearchItem,
  StockSentiment,
  StockValuationDetail,
  TechnicalIndicators,
} from "../../types/stock";

export function useStockSearch(query: string) {
  return useQuery({
    queryKey: queryKeys.stock.search(query),
    queryFn: () => openApiGet("/api/stock/search", {
      query: { q: query },
    }),
    select: asApiModel<StockSearchItem[]>(),
    enabled: query.length >= 1,
    staleTime: 5 * 60 * 1000,
    placeholderData: (previous) => previous,
  });
}

export function useKlineData(
  code: string,
  period = "daily",
  adjust = "qfq",
  enabled = true,
  dateRange?: { startDate: string; endDate?: string },
) {
  const startDate = dateRange?.startDate || oneYearAgoDate();
  const endDate = dateRange?.endDate || "";

  return useQuery({
    queryKey: queryKeys.stock.kline(code, period, adjust, startDate, endDate),
    queryFn: () => openApiGet("/api/stock/{code}/kline", {
      path: { code },
      query: { period, adjust, start_date: startDate, end_date: endDate },
    }),
    select: asApiModel<KlineData>(),
    enabled: enabled && !!code,
    staleTime: 5 * 60 * 1000,
  });
}

export function useStockIntraday(code: string, initialData?: IntradayData | null) {
  const isTradingSession = useAStockTradingSession();
  return useQuery({
    queryKey: queryKeys.stock.intraday(code),
    queryFn: () => openApiGet("/api/stock/{code}/intraday", {
      path: { code },
    }),
    select: asApiModel<IntradayData>(),
    enabled: Boolean(code),
    initialData: initialData ?? undefined,
    staleTime: QUERY_CACHE_POLICIES.stockIntraday.staleMs,
    refetchInterval: isTradingSession ? QUERY_CACHE_POLICIES.stockIntraday.pollMs : false,
  });
}

export function useFinancial(code: string, type = "balance") {
  return useQuery({
    queryKey: queryKeys.stock.financial(code, type),
    queryFn: () => openApiGet("/api/stock/{code}/financial", {
      path: { code },
      query: { type },
    }),
    select: asApiModel<Record<string, unknown>[]>(),
    enabled: !!code,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useValuationDetail(code: string) {
  return useQuery({
    queryKey: queryKeys.stock.valuationDetail(code),
    queryFn: () => openApiGet("/api/stock/{code}/valuation-detail", {
      path: { code },
    }),
    select: asApiModel<StockValuationDetail>(),
    enabled: !!code,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useIndicators(code: string) {
  return useQuery({
    queryKey: queryKeys.stock.indicators(code),
    queryFn: () => openApiGet("/api/stock/{code}/indicators", {
      path: { code },
    }),
    select: asApiModel<TechnicalIndicators>(),
    enabled: !!code,
    staleTime: 5 * 60 * 1000,
  });
}

export function useCategorizedStockNews(code: string) {
  return useQuery({
    queryKey: queryKeys.stock.categorizedNews(code),
    queryFn: () => openApiGet("/api/stock/{code}/news-categorized", {
      path: { code },
    }),
    select: asApiModel<CategorizedStockNews>(),
    enabled: !!code,
    staleTime: 10 * 60 * 1000,
  });
}

export function useStockSentiment(code: string) {
  return useQuery({
    queryKey: queryKeys.stock.sentiment(code),
    queryFn: () => openApiGet("/api/stock/{code}/sentiment", {
      path: { code },
    }),
    select: asApiModel<StockSentiment>(),
    enabled: !!code,
    staleTime: 10 * 60 * 1000,
  });
}

export function useRetailSentiment(code: string) {
  return useQuery({
    queryKey: queryKeys.stock.retailSentiment(code),
    queryFn: () => openApiGet("/api/stock/{code}/retail-sentiment", {
      path: { code },
    }),
    select: asApiModel<RetailSentiment>(),
    enabled: !!code,
    staleTime: 10 * 60 * 1000,
  });
}

export function useStockCompare(codes: string) {
  return useQuery({
    queryKey: queryKeys.stock.compare(codes),
    queryFn: () => openApiGet("/api/stock/compare", {
      query: { codes },
    }),
    select: asApiModel<StockCompareItem[]>(),
    enabled: codes.length > 0,
    staleTime: 5 * 60 * 1000,
  });
}

export function useStockFundFlow(code: string) {
  return useQuery({
    queryKey: queryKeys.stock.fundFlow(code),
    queryFn: () => openApiGet("/api/stock/{code}/fund-flow", {
      path: { code },
    }),
    select: asApiModel<StockFundFlowItem[]>(),
    enabled: !!code,
    staleTime: 5 * 60 * 1000,
  });
}

export function useAnalysisPageData(code: string) {
  return useQuery({
    queryKey: queryKeys.stock.analysisPage(code),
    queryFn: () => openApiGet("/api/stock/analysis-page/{code}", {
      path: { code },
    }),
    select: asApiModel<AnalysisPageData>(),
    enabled: !!code,
    staleTime: 5 * 60 * 1000,
  });
}
