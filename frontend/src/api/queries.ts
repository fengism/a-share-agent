import { useQuery, useMutation } from "@tanstack/react-query";
import { apiGet, apiPost, apiPut } from "./client";
import { oneYearAgoDate } from "../utils/date";
import type { StockSearchItem, StockBasicInfo, KlineData, IntradayData, FinancialMetrics, StockValuation, StockValuationDetail, AnalysisResult, AnalysisHistoryItem, TechnicalIndicators, MarketIndices, HsgtFlow, StockNews, CategorizedStockNews, StockSentiment, RetailSentiment, ScreenerFilter, ScreenerResult, ValuationPercentileRequest, ValuationPercentileResult, ThsHotStock, ThsHotPlate, DragonTigerItem, DragonTigerDetail, PushRequest, PushResponse, FeedNewsItem, IndustryRankings, NewsAnalysis, IndustryChainResult, IndustryChainHistoryItem } from "../types/stock";
import type { DailyReviewHistoryItem, DailyReviewRequest, DailyReviewResult } from "../types/dailyReview";
import type { ConfigData, ConfigUpdate } from "../types/settings";

export function useStockSearch(query: string) {
  return useQuery({
    queryKey: ["stockSearch", query],
    queryFn: () => apiGet<StockSearchItem[]>("/stock/search", { q: query }),
    enabled: query.length >= 1,
    staleTime: 5 * 60 * 1000,
    placeholderData: (prev) => prev,
  });
}

export function useStockInfo(code: string) {
  return useQuery({
    queryKey: ["stockInfo", code],
    queryFn: () => apiGet<StockBasicInfo>(`/stock/${code}/info`),
    enabled: !!code,
    staleTime: 5 * 60 * 1000,
  });
}

export function useKlineData(code: string, period = "daily", adjust = "qfq") {
  const startDate = oneYearAgoDate();

  return useQuery({
    queryKey: ["kline", code, period, adjust, startDate],
    queryFn: () =>
      apiGet<KlineData>(`/stock/${code}/kline`, {
        period,
        adjust,
        start_date: startDate,
      }),
    enabled: !!code,
    staleTime: 5 * 60 * 1000,
  });
}

export function useIntradayData(code: string) {
  return useQuery({
    queryKey: ["intraday", code],
    queryFn: () => apiGet<IntradayData>(`/stock/${code}/intraday`),
    enabled: !!code,
    staleTime: 5 * 60 * 1000,
  });
}

export function useFinancial(code: string, type = "balance") {
  return useQuery({
    queryKey: ["financial", code, type],
    queryFn: () => apiGet<Record<string, unknown>[]>(`/stock/${code}/financial`, { type }),
    enabled: !!code,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useValuation(code: string) {
  return useQuery({
    queryKey: ["valuation", code],
    queryFn: () => apiGet<StockValuation>(`/stock/${code}/valuation`),
    enabled: !!code,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useValuationDetail(code: string) {
  return useQuery({
    queryKey: ["valuationDetail", code],
    queryFn: () => apiGet<StockValuationDetail>(`/stock/${code}/valuation-detail`),
    enabled: !!code,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useFinancialMetrics(code: string) {
  return useQuery({
    queryKey: ["financialMetrics", code],
    queryFn: () => apiGet<FinancialMetrics>(`/stock/${code}/financial-metrics`),
    enabled: !!code,
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useIndicators(code: string) {
  return useQuery({
    queryKey: ["indicators", code],
    queryFn: () => apiGet<TechnicalIndicators>(`/stock/${code}/indicators`),
    enabled: !!code,
    staleTime: 5 * 60 * 1000,
  });
}

export function useStockNews(code: string) {
  return useQuery({
    queryKey: ["news", code],
    queryFn: () => apiGet<StockNews[]>(`/stock/${code}/news`),
    enabled: !!code,
    staleTime: 10 * 60 * 1000,
  });
}

export function useCategorizedStockNews(code: string) {
  return useQuery({
    queryKey: ["categorizedNews", code],
    queryFn: () => apiGet<CategorizedStockNews>(`/market/news-categorized`, { code }),
    enabled: !!code,
    staleTime: 10 * 60 * 1000,
  });
}

export function useMarketIndices() {
  return useQuery({
    queryKey: ["marketIndices"],
    queryFn: () => apiGet<MarketIndices>("/market/indices"),
    staleTime: 5 * 60 * 1000,
  });
}

export function useMarketIndexKline(symbol: string, period = "daily") {
  const startDate = oneYearAgoDate();

  return useQuery({
    queryKey: ["marketIndexKline", symbol, period, startDate],
    queryFn: () =>
      apiGet<KlineData>("/market/index-kline", {
        symbol,
        period,
        start_date: startDate,
      }),
    enabled: !!symbol,
    staleTime: 5 * 60 * 1000,
  });
}

export function useHsgtFlow(enabled = true, autoRefresh = true) {
  return useQuery({
    queryKey: ["hsgtFlow"],
    queryFn: () => apiGet<HsgtFlow>("/market/hsgt-flow"),
    enabled,
    staleTime: 60 * 1000,
    refetchInterval: enabled && autoRefresh ? 60 * 1000 : false,
  });
}

export function useHotStocks() {
  return useQuery({
    queryKey: ["hotStocks"],
    queryFn: () => apiGet<Record<string, unknown>[]>("/market/hot-stocks"),
    staleTime: 5 * 60 * 1000,
  });
}

export function useStockSentiment(code: string) {
  return useQuery({
    queryKey: ["sentiment", code],
    queryFn: () => apiGet<StockSentiment>(`/market/sentiment`, { code }),
    enabled: !!code,
    staleTime: 10 * 60 * 1000,
  });
}

export function useRetailSentiment(code: string) {
  return useQuery({
    queryKey: ["retailSentiment", code],
    queryFn: () => apiGet<RetailSentiment>(`/market/retail-sentiment`, { code }),
    enabled: !!code,
    staleTime: 10 * 60 * 1000,
  });
}

export function useTriggerAnalysis() {
  return useMutation({
    mutationFn: (code: string) => apiPost<AnalysisResult>(`/analysis/${code}`),
  });
}

export function useDailyReviewHistory() {
  return useQuery({
    queryKey: ["dailyReviewHistory"],
    queryFn: () => apiGet<DailyReviewHistoryItem[]>("/daily-review/history"),
    staleTime: 5 * 60 * 1000,
  });
}

export function useDailyReview(date: string) {
  return useQuery({
    queryKey: ["dailyReview", date],
    queryFn: () => apiGet<DailyReviewResult>(`/daily-review/${date}`),
    enabled: !!date,
    staleTime: 5 * 60 * 1000,
  });
}

export function useGenerateDailyReview() {
  return useMutation({
    mutationFn: (req: DailyReviewRequest) => apiPost<DailyReviewResult>("/daily-review/generate", req),
  });
}

export function usePush() {
  return useMutation({
    mutationFn: (req: PushRequest) =>
      apiPost<PushResponse>("/push", req),
  });
}

export function useAnalysisResult(code: string) {
  return useQuery({
    queryKey: ["analysisResult", code],
    queryFn: () => apiGet<AnalysisResult>(`/analysis/${code}/result`),
    enabled: !!code,
    staleTime: 4 * 60 * 60 * 1000,
  });
}

export function useAnalysisHistory(code: string) {
  return useQuery({
    queryKey: ["analysisHistory", code],
    queryFn: () => apiGet<AnalysisHistoryItem[]>(`/analysis/${code}/history`),
    enabled: !!code,
    staleTime: 5 * 60 * 1000,
  });
}

export function useAllAnalysisHistory() {
  return useQuery({
    queryKey: ["allAnalysisHistory"],
    queryFn: () => apiGet<AnalysisHistoryItem[]>("/analysis/history/all"),
    staleTime: 5 * 60 * 1000,
  });
}

// Screener
export function useScreenerScreen(filters: ScreenerFilter, enabled = true) {
  return useQuery({
    queryKey: ["screener", filters],
    queryFn: () => apiPost<ScreenerResult>("/screener/screen", filters),
    enabled,
    staleTime: 2 * 60 * 1000,
  });
}

export function useIndustries() {
  return useQuery({
    queryKey: ["industries"],
    queryFn: () => apiGet<string[]>("/screener/industries"),
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useComputePercentiles() {
  return useMutation({
    mutationFn: (req: ValuationPercentileRequest) =>
      apiPost<ValuationPercentileResult>("/screener/percentile", req),
  });
}

// Hot Rank
export function useThsHotRank(enabled = true) {
  return useQuery({
    queryKey: ["thsHotRank"],
    queryFn: () => apiGet<ThsHotStock[]>("/market/hot-rank/ths"),
    enabled,
    staleTime: 60 * 1000,
    refetchInterval: enabled ? 60 * 1000 : false,
  });
}

export function useThsHotConcept(enabled = true) {
  return useQuery({
    queryKey: ["thsHotConcept"],
    queryFn: () => apiGet<ThsHotPlate[]>("/market/hot-rank/ths/concept"),
    enabled,
    staleTime: 60 * 1000,
    refetchInterval: enabled ? 60 * 1000 : false,
  });
}

export function useThsHotIndustry(enabled = true) {
  return useQuery({
    queryKey: ["thsHotIndustry"],
    queryFn: () => apiGet<ThsHotPlate[]>("/market/hot-rank/ths/industry"),
    enabled,
    staleTime: 60 * 1000,
    refetchInterval: enabled ? 60 * 1000 : false,
  });
}

export function useIndustryRankings() {
  return useQuery({
    queryKey: ["industryRankings"],
    queryFn: () => apiGet<IndustryRankings>("/market/industry-rankings"),
    staleTime: 5 * 60 * 1000,
  });
}

// Dragon Tiger
export function useDragonTigerList(reportDate: string) {
  return useQuery({
    queryKey: ["dragonTiger", reportDate],
    queryFn: () => apiGet<DragonTigerItem[]>("/market/dragon-tiger", { report_date: reportDate }),
    enabled: !!reportDate,
    staleTime: 10 * 60 * 1000,
  });
}

export function useDragonTigerDetail(code: string, reportDate: string) {
  return useQuery({
    queryKey: ["dragonTigerDetail", code, reportDate],
    queryFn: () => apiGet<DragonTigerDetail[]>(`/market/dragon-tiger/${code}`, { report_date: reportDate }),
    enabled: !!code && !!reportDate,
    staleTime: 10 * 60 * 1000,
  });
}

// Config
export function useConfig() {
  return useQuery({
    queryKey: ["config"],
    queryFn: () => apiGet<ConfigData>("/config"),
    staleTime: 0,
  });
}

export function useUpdateConfig() {
  return useMutation({
    mutationFn: (patch: ConfigUpdate) => apiPut<ConfigData>("/config", patch),
  });
}

export function useMarketFeed() {
  return useQuery({
    queryKey: ["marketFeed"],
    queryFn: () => apiGet<FeedNewsItem[]>("/market/feed"),
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
  });
}

export function useMarketKuaixun() {
  return useQuery({
    queryKey: ["marketKuaixun"],
    queryFn: () => apiGet<FeedNewsItem[]>("/market/kuaixun"),
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
  });
}

export function useMarketOtherNews() {
  return useQuery({
    queryKey: ["marketOtherNews"],
    queryFn: () => apiGet<FeedNewsItem[]>("/market/other-news"),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });
}

export function useMarketTwitterFeed() {
  return useQuery({
    queryKey: ["marketTwitterFeed"],
    queryFn: () => apiGet<FeedNewsItem[]>("/market/twitter-feed"),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });
}

export function useNewsAnalysis() {
  return useQuery({
    queryKey: ["newsAnalysis"],
    queryFn: () => apiGet<NewsAnalysis>("/market/news-analysis"),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });
}

export function useIndustryChainHistory(name = "") {
  return useQuery({
    queryKey: ["industryChainHistory", name],
    queryFn: () =>
      apiGet<IndustryChainHistoryItem[]>(
        "/industry-chain/history",
        name ? { name } : {}
      ),
    staleTime: 30 * 1000,
  });
}

export function useIndustryChainLatest(name: string) {
  return useQuery({
    queryKey: ["industryChainLatest", name],
    queryFn: () => apiGet<{ archive_id: string; saved_at: string }>(`/industry-chain/${encodeURIComponent(name)}/latest`),
    enabled: !!name,
    staleTime: 30 * 1000,
  });
}

export function useIndustryChainArchive() {
  return useMutation({
    mutationFn: ({ name, archiveId }: { name: string; archiveId: string }) =>
      apiGet<IndustryChainResult>(
        `/industry-chain/${encodeURIComponent(name)}/archive/${archiveId}`
      ),
  });
}
