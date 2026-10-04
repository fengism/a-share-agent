import { useInfiniteQuery, useQuery, type QueryClient } from "@tanstack/react-query";
import { QUERY_CACHE_POLICIES } from "../cachePolicies";
import { API_TIMEOUTS } from "../client";
import { asApiModel, openApiGet } from "../openapiClient";
import { queryKeys } from "../queryKeys";
import { oneYearAgoDate } from "../../utils/date";
import { useAStockTradingSession } from "../../hooks/useAStockTradingSession";
import type {
  AnalysisPageData,
  CategorizedStockNews,
  ChipDistribution,
  FundamentalExportData,
  IntradayData,
  KlineData,
  RetailSentiment,
  RevenueBreakdown,
  StockBasicInfo,
  StockBulletinPage,
  StockBusinessIntro,
  StockFundFlowItem,
  StockFundFlowPage,
  StockReportPage,
  StockSearchItem,
  StockSentiment,
  StockValuationDetail,
  TechnicalIndicators,
} from "../../types/stock";

export function useStockInfo(code: string, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.stock.info(code),
    queryFn: () => openApiGet("/api/stock/{code}/info", {
      path: { code },
    }),
    select: asApiModel<StockBasicInfo>(),
    enabled: !!code && (options.enabled ?? true),
    staleTime: QUERY_CACHE_POLICIES.reference.staleMs,
  });
}

export function useStockBusinessIntro(code: string) {
  return useQuery({
    queryKey: queryKeys.stock.businessIntro(code),
    queryFn: () => openApiGet("/api/stock/{code}/business-intro", {
      path: { code },
    }),
    select: asApiModel<StockBusinessIntro>(),
    enabled: !!code,
    staleTime: QUERY_CACHE_POLICIES.reference.staleMs,
  });
}

export function useStockChipDistribution(code: string) {
  return useQuery({
    queryKey: queryKeys.stock.chipDistribution(code),
    queryFn: () => openApiGet("/api/stock/{code}/chip-distribution", {
      path: { code },
    }),
    select: asApiModel<ChipDistribution>(),
    enabled: !!code,
    staleTime: QUERY_CACHE_POLICIES.marketTenMinutes.staleMs,
  });
}

export function useStockSearch(query: string) {
  return useQuery({
    queryKey: queryKeys.stock.search(query),
    queryFn: ({ signal }) => openApiGet("/api/stock/search", {
      query: { q: query },
      options: { signal },
    }),
    select: asApiModel<StockSearchItem[]>(),
    enabled: query.length >= 1,
    staleTime: QUERY_CACHE_POLICIES.marketMinute.staleMs,
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
  // 空串会被 API 客户端当作"未传"丢弃，后端会套用默认 qfq，表现为选不复权仍显示前复权价；
  // 这里显式发 none，与港股接口约定一致。
  const adjustParam = adjust || "none";

  return useQuery({
    queryKey: queryKeys.stock.kline(code, period, adjust, startDate, endDate),
    queryFn: () => openApiGet("/api/stock/{code}/kline", {
      path: { code },
      query: { period, adjust: adjustParam, start_date: startDate, end_date: endDate },
    }),
    select: asApiModel<KlineData>(),
    enabled: enabled && !!code,
    staleTime: QUERY_CACHE_POLICIES.marketTenMinutes.staleMs,
    // 向左扩充历史时保留上一批数据，避免图表闪空
    placeholderData: (previous) => previous,
  });
}

export function useStockIntraday(code: string, initialData?: IntradayData | null, options: { enabled?: boolean } = {}) {
  const isTradingSession = useAStockTradingSession();
  return useQuery({
    queryKey: queryKeys.stock.intraday(code),
    queryFn: () => openApiGet("/api/stock/{code}/intraday", {
      path: { code },
    }),
    select: asApiModel<IntradayData>(),
    enabled: Boolean(code) && (options.enabled ?? true),
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
    staleTime: QUERY_CACHE_POLICIES.reference.staleMs,
  });
}

const REVENUE_BREAKDOWN_STALE_TIME = QUERY_CACHE_POLICIES.reference.staleMs;

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
    staleTime: QUERY_CACHE_POLICIES.marketDaily.staleMs,
  });
}

export function useIndicators(
  code: string,
  period = "daily",
  options: { startDate?: string; endDate?: string; enabled?: boolean } = {},
) {
  const startDate = options.startDate ?? "";
  const endDate = options.endDate ?? "";
  return useQuery({
    queryKey: queryKeys.stock.indicators(code, period, startDate, endDate),
    queryFn: () => openApiGet("/api/stock/{code}/indicators", {
      path: { code },
      query: {
        period,
        ...(startDate ? { start_date: startDate } : {}),
        ...(endDate ? { end_date: endDate } : {}),
      },
    }),
    select: asApiModel<TechnicalIndicators>(),
    enabled: !!code && (options.enabled ?? true),
    staleTime: QUERY_CACHE_POLICIES.marketMinute.staleMs,
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
    staleTime: QUERY_CACHE_POLICIES.marketTenMinutes.staleMs,
  });
}

export function useStockBulletins(code: string, page: number, pageSize = 10) {
  return useQuery({
    queryKey: queryKeys.stock.bulletins(code, page, pageSize),
    queryFn: ({ signal }) => openApiGet("/api/stock/{code}/bulletins", {
      path: { code },
      query: { page, page_size: pageSize },
      options: { signal },
    }),
    select: asApiModel<StockBulletinPage>(),
    enabled: !!code,
    staleTime: QUERY_CACHE_POLICIES.marketThirtyMinutes.staleMs,
    placeholderData: (previous) => previous,
  });
}

export function useStockReports(code: string, months = 6) {
  return useQuery({
    queryKey: queryKeys.stock.reports(code, months),
    queryFn: ({ signal }) => openApiGet("/api/stock/{code}/reports", {
      path: { code },
      query: { months },
      options: { signal },
    }),
    select: asApiModel<StockReportPage>(),
    enabled: !!code,
    staleTime: QUERY_CACHE_POLICIES.marketThirtyMinutes.staleMs,
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
    staleTime: QUERY_CACHE_POLICIES.marketTenMinutes.staleMs,
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
    staleTime: QUERY_CACHE_POLICIES.marketTenMinutes.staleMs,
  });
}

export function useStockFundFlow(code: string) {
  return useQuery({
    queryKey: queryKeys.stock.fundFlow(code),
    queryFn: () => openApiGet("/api/stock/{code}/fund-flow", {
      path: { code },
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<StockFundFlowItem[]>(),
    enabled: !!code,
    staleTime: QUERY_CACHE_POLICIES.marketMinute.staleMs,
  });
}

export function useStockFundFlowPages(code: string) {
  return useInfiniteQuery({
    queryKey: queryKeys.stock.fundFlowPages(code),
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => openApiGet("/api/stock/{code}/fund-flow-pages", {
      path: { code }, query: pageParam ? { cursor: pageParam } : undefined,
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }).then(asApiModel<StockFundFlowPage>()),
    getNextPageParam: (page) => page.next_cursor ?? undefined,
    enabled: !!code,
    staleTime: QUERY_CACHE_POLICIES.marketMinute.staleMs,
    retry: false,
  });
}

export function useAnalysisSnapshot(code: string, options: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: queryKeys.stock.analysisPage(code),
    queryFn: () => openApiGet("/api/stock/analysis-page/{code}", {
      path: { code },
      query: { include_market_data: false },
    }),
    select: asApiModel<AnalysisPageData>(),
    enabled: !!code && (options.enabled ?? true),
    staleTime: QUERY_CACHE_POLICIES.marketMinute.staleMs,
  });
}

export function useAnalysisPageData(code: string, options: { enabled?: boolean } = {}) {
  // Share identity, live price and headline valuation with the stock profile.
  // The analysis endpoint only loads the user's cached research result.
  const info = useStockInfo(code, options);
  const intraday = useStockIntraday(code, undefined, options);
  const snapshot = useAnalysisSnapshot(code, options);
  const unavailable = new Set<NonNullable<AnalysisPageData["unavailable_sections"]>[number]>(
    (snapshot.data?.unavailable_sections ?? []).filter((section) => section === "cached_analysis"),
  );
  if (snapshot.isError) unavailable.add("cached_analysis");
  if (info.isError) unavailable.add("stock_info");
  if (intraday.isError) unavailable.add("intraday");
  const data: AnalysisPageData | undefined = snapshot.data || info.data ? {
    stock_info: info.data ?? null,
    intraday: intraday.data ?? null,
    valuation: info.data ? {
      code,
      pe_ttm: info.data.pe_ttm,
      pb: info.data.pb,
      ps_ttm: null,
      peers: [],
    } : null,
    cached_analysis: snapshot.data?.cached_analysis ?? null,
    kline: null,
    key_levels: null,
    chip_distribution: null,
    partial: unavailable.size > 0,
    unavailable_sections: [...unavailable],
  } : undefined;
  return {
    ...snapshot,
    data,
    isLoading: snapshot.isLoading || info.isLoading,
    isError: snapshot.isError || info.isError,
    error: snapshot.error ?? info.error,
    refetch: () => Promise.all([snapshot.refetch(), info.refetch(), intraday.refetch()]),
  };
}

export async function downloadAnalysisPdf(code: string, date?: string): Promise<void> {
  const { apiDownload } = await import("../client");
  const fallback = `${code}_深度投研报告.pdf`;
  await apiDownload(`/analysis/${code}/export-pdf`, fallback, { date });
}

export async function downloadAnalysisPdfFromData(result: unknown): Promise<void> {
  const { apiDownloadPost } = await import("../client");
  const res = result as { code?: string; stock_code?: string; name?: string; stock_name?: string };
  const code = res?.stock_code || res?.code || "stock";
  const name = res?.stock_name || res?.name || code;
  const fallback = `${code}_${name}_深度投研报告.pdf`;
  await apiDownloadPost("/analysis/export-pdf", result, fallback);
}
