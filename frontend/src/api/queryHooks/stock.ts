import { useQuery } from "@tanstack/react-query";
import { apiGet } from "../client";
import { queryKeys } from "../queryKeys";
import { oneYearAgoDate } from "../../utils/date";
import type {
  CategorizedStockNews,
  KlineData,
  RetailSentiment,
  StockCompareItem,
  StockFundFlowItem,
  StockSearchItem,
  StockSentiment,
  StockValuationDetail,
  TechnicalIndicators,
  AnalysisPageData,
} from "../../types/stock";

export function useStockSearch(query: string) {
  return useQuery({
    queryKey: queryKeys.stock.search(query),
    queryFn: ({ signal }) => apiGet<StockSearchItem[]>("/stock/search", { q: query }, { signal }),
    enabled: query.length >= 1,
    staleTime: 5 * 60 * 1000,
    placeholderData: (prev) => prev,
  });
}

export function useKlineData(code: string, period = "daily", adjust = "qfq", enabled = true) {
  const startDate = oneYearAgoDate();

  return useQuery({
    queryKey: queryKeys.stock.kline(code, period, adjust, startDate),
    queryFn: ({ signal }) =>
      apiGet<KlineData>(`/stock/${code}/kline`, {
        period,
        adjust,
        start_date: startDate,
      }, { signal }),
    enabled: enabled && !!code,
    staleTime: 5 * 60 * 1000,
  });
}

export function useFinancial(code: string, type = "balance") {
  return useQuery({
    queryKey: queryKeys.stock.financial(code, type),
    queryFn: ({ signal }) => apiGet<Record<string, unknown>[]>(`/stock/${code}/financial`, { type }, { signal }),
    enabled: !!code,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useValuationDetail(code: string) {
  return useQuery({
    queryKey: queryKeys.stock.valuationDetail(code),
    queryFn: ({ signal }) => apiGet<StockValuationDetail>(`/stock/${code}/valuation-detail`, undefined, { signal }),
    enabled: !!code,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useIndicators(code: string) {
  return useQuery({
    queryKey: queryKeys.stock.indicators(code),
    queryFn: ({ signal }) => apiGet<TechnicalIndicators>(`/stock/${code}/indicators`, undefined, { signal }),
    enabled: !!code,
    staleTime: 5 * 60 * 1000,
  });
}

export function useCategorizedStockNews(code: string) {
  return useQuery({
    queryKey: queryKeys.stock.categorizedNews(code),
    queryFn: ({ signal }) => apiGet<CategorizedStockNews>(`/stock/${code}/news-categorized`, undefined, { signal }),
    enabled: !!code,
    staleTime: 10 * 60 * 1000,
  });
}

export function useStockSentiment(code: string) {
  return useQuery({
    queryKey: queryKeys.stock.sentiment(code),
    queryFn: ({ signal }) => apiGet<StockSentiment>(`/stock/${code}/sentiment`, undefined, { signal }),
    enabled: !!code,
    staleTime: 10 * 60 * 1000,
  });
}

export function useRetailSentiment(code: string) {
  return useQuery({
    queryKey: queryKeys.stock.retailSentiment(code),
    queryFn: ({ signal }) => apiGet<RetailSentiment>(`/stock/${code}/retail-sentiment`, undefined, { signal }),
    enabled: !!code,
    staleTime: 10 * 60 * 1000,
  });
}

export function useStockCompare(codes: string) {
  return useQuery({
    queryKey: queryKeys.stock.compare(codes),
    queryFn: ({ signal }) => apiGet<StockCompareItem[]>("/stock/compare", { codes }, { signal }),
    enabled: codes.length > 0,
    staleTime: 5 * 60 * 1000,
  });
}

export function useStockFundFlow(code: string) {
  return useQuery({
    queryKey: queryKeys.stock.fundFlow(code),
    queryFn: ({ signal }) => apiGet<StockFundFlowItem[]>(`/stock/${code}/fund-flow`, undefined, { signal }),
    enabled: !!code,
    staleTime: 5 * 60 * 1000,
  });
}

export function useAnalysisPageData(code: string) {
  return useQuery({
    queryKey: queryKeys.stock.analysisPage(code),
    queryFn: ({ signal }) => apiGet<AnalysisPageData>(
      `/stock/analysis-page/${code}`,
      undefined,
      { signal },
    ),
    enabled: !!code,
    staleTime: 5 * 60 * 1000,
  });
}
