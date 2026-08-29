import { useQuery, type QueryClient } from "@tanstack/react-query";
import { QUERY_CACHE_POLICIES } from "../cachePolicies";
import { API_TIMEOUTS } from "../client";
import { asApiModel, openApiGet } from "../openapiClient";
import { queryKeys } from "../queryKeys";
import { oneYearAgoDate } from "../../utils/date";
import { useAStockTradingSession } from "../../hooks/useAStockTradingSession";
import type {
  AnalysisPageData,
  CategorizedStockNews,
  FundamentalExportData,
  IntradayData,
  KlineData,
  RetailSentiment,
  RevenueBreakdown,
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
    queryFn: ({ signal }) => openApiGet("/api/stock/search", {
      query: { q: query },
      options: { signal },
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

export function useFinancial(code: string, type: "balance" | "profit" | "cashflow" = "balance") {
  return useQuery({
    queryKey: queryKeys.stock.financial(code, type),
    queryFn: () => fetchFinancial(code, type),
    select: asApiModel<Record<string, unknown>[]>(),
    enabled: !!code,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

const REVENUE_BREAKDOWN_STALE_TIME = 24 * 60 * 60 * 1000;

function fetchFinancial(code: string, type: "balance" | "profit" | "cashflow") {
  return openApiGet("/api/stock/{code}/financial", {
    path: { code },
    query: { type },
    options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
  });
}

function fetchRevenueBreakdown(code: string) {
  return openApiGet("/api/stock/{code}/revenue-breakdown", {
    path: { code },
    options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
  });
}

export function useRevenueBreakdown(code: string) {
  return useQuery({
    queryKey: queryKeys.stock.revenueBreakdown(code),
    queryFn: () => fetchRevenueBreakdown(code),
    select: asApiModel<RevenueBreakdown>(),
    enabled: !!code,
    staleTime: REVENUE_BREAKDOWN_STALE_TIME,
  });
}

export async function ensureFundamentalData(queryClient: QueryClient, code: string) {
  if (!code) throw new Error("PDF 导出缺少股票代码");
  const [balance, profit, cashflow, revenueBreakdown] = await Promise.all([
    ...(["balance", "profit", "cashflow"] as const).map((type) => queryClient.fetchQuery({
      queryKey: queryKeys.stock.financial(code, type),
      queryFn: () => fetchFinancial(code, type),
      staleTime: 0,
    })),
    queryClient.fetchQuery({
      queryKey: queryKeys.stock.revenueBreakdown(code),
      queryFn: () => fetchRevenueBreakdown(code),
      staleTime: 0,
    }),
  ]);

  const snapshot: FundamentalExportData = {
    balance: balance as Record<string, unknown>[],
    profit: profit as Record<string, unknown>[],
    cashflow: cashflow as Record<string, unknown>[],
    revenueBreakdown: revenueBreakdown as RevenueBreakdown,
  };
  const missingSections = [
    snapshot.balance.length === 0 ? "资产负债表" : null,
    snapshot.profit.length === 0 ? "利润表" : null,
    snapshot.cashflow.length === 0 ? "现金流量表" : null,
    (
      snapshot.revenueBreakdown.by_product.length
      + snapshot.revenueBreakdown.by_business.length
      + snapshot.revenueBreakdown.by_region.length
    ) === 0 ? "营收与毛利构成" : null,
  ].filter((label): label is string => Boolean(label));
  if (missingSections.length > 0) {
    throw new Error(`PDF 导出所需财务数据不完整：${missingSections.join("、")}暂无数据`);
  }
  return snapshot;
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

export function useAnalysisPageData(code: string, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.stock.analysisPage(code),
    queryFn: () => openApiGet("/api/stock/analysis-page/{code}", {
      path: { code },
    }),
    select: asApiModel<AnalysisPageData>(),
    enabled: !!code && (options.enabled ?? true),
    staleTime: 5 * 60 * 1000,
  });
}
