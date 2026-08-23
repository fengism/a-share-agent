import { queryOptions, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import dayjs from "dayjs";
import { QUERY_CACHE_POLICIES } from "../cachePolicies";
import { API_TIMEOUTS } from "../client";
import { asApiModel, openApiGet, openApiPost } from "../openapiClient";
import { queryKeys } from "../queryKeys";
import { oneYearAgoDate } from "../../utils/date";
import { useAStockTradingSession } from "../../hooks/useAStockTradingSession";
import type {
  DragonTigerDetail,
  DragonTigerItem,
  FeedNewsItem,
  HsgtFlow,
  IndustryRankings,
  IndexIntradayData,
  KlineData,
  MarketEmotion,
  MarketLimitHistory,
  MarketLimitHistoryCategory,
  MarketLimitUpLadder,
  MarketMainline,
  MarketMargin,
  MarketSectorStocksHistory,
  MarketWind,
  MarketWindStocks,
  MacroAllData,
  MacroUsData,
  MarketIndices,
  NewsAnalysis,
  ThsHotPlate,
  ThsHotStock,
  TradingCalendar,
} from "../../types/stock";

export function marketIndicesQueryOptions(refetchInterval: number | false = false) {
  return queryOptions({
    queryKey: queryKeys.market.indices,
    queryFn: () => openApiGet("/api/market/indices", {
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<MarketIndices>(),
    staleTime: QUERY_CACHE_POLICIES.marketIndices.staleMs,
    refetchInterval,
    refetchOnWindowFocus: true,
  });
}

export function useMarketIndices() {
  const isTradingSession = useAStockTradingSession();
  return useQuery(marketIndicesQueryOptions(
    isTradingSession ? QUERY_CACHE_POLICIES.marketIndices.pollMs : false,
  ));
}

export function useMarketEmotion() {
  const isTradingSession = useAStockTradingSession();
  return useQuery({
    queryKey: queryKeys.market.emotion,
    queryFn: () => openApiGet("/api/market/emotion", {
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<MarketEmotion>(),
    staleTime: 60 * 1000,
    refetchInterval: isTradingSession ? 60 * 1000 : false,
  });
}

export function useMarketLimitUpLadder(date: string) {
  const isTradingSession = useAStockTradingSession();
  return useQuery({
    queryKey: queryKeys.market.limitUpLadder(date),
    queryFn: () => openApiGet("/api/market/limit-up-ladder", {
      query: { date },
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<MarketLimitUpLadder>(),
    enabled: Boolean(date),
    staleTime: 60 * 1000,
    refetchInterval: isTradingSession ? 60 * 1000 : false,
  });
}

export function useMarketLimitHistory(date: string, category: MarketLimitHistoryCategory) {
  return useQuery({
    queryKey: queryKeys.market.limitHistory(date, category),
    queryFn: () => openApiGet("/api/market/limit-history", {
      query: { date, category },
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<MarketLimitHistory>(),
    enabled: Boolean(date && category),
    staleTime: QUERY_CACHE_POLICIES.marketLimitHistory.staleMs,
  });
}

export function useMarketSectorStocksHistory(date: string, plateId: string) {
  return useQuery({
    queryKey: queryKeys.market.sectorStocksHistory(date, plateId),
    queryFn: () => openApiGet("/api/market/sector-stocks-history", {
      query: { date, plate_id: plateId },
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<MarketSectorStocksHistory>(),
    enabled: Boolean(date && plateId),
    staleTime: QUERY_CACHE_POLICIES.marketSectorStocksHistory.staleMs,
  });
}

export function useMarketWind() {
  const isTradingSession = useAStockTradingSession();
  return useQuery({
    queryKey: queryKeys.market.wind,
    queryFn: () => openApiGet("/api/market/today-wind", {
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<MarketWind>(),
    staleTime: 60 * 1000,
    refetchInterval: isTradingSession ? 60 * 1000 : false,
  });
}

export function useMarketMainline() {
  const isTradingSession = useAStockTradingSession();
  return useQuery({
    queryKey: queryKeys.market.mainline,
    queryFn: () => openApiGet("/api/market/mainline", {
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<MarketMainline>(),
    staleTime: 60 * 1000,
    refetchInterval: isTradingSession ? 60 * 1000 : false,
  });
}

export function useMarketWindStocks(plateCode: string) {
  const isTradingSession = useAStockTradingSession();
  return useQuery({
    queryKey: queryKeys.market.windStocks(plateCode),
    queryFn: () => openApiGet("/api/market/today-wind/{plate_code}/stocks", {
      path: { plate_code: plateCode },
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<MarketWindStocks>(),
    enabled: Boolean(plateCode),
    staleTime: 60 * 1000,
    refetchInterval: isTradingSession ? 60 * 1000 : false,
  });
}

export function useMarketIndexIntraday(symbol: string) {
  const isTradingSession = useAStockTradingSession();
  return useQuery({
    queryKey: queryKeys.market.indexIntraday(symbol),
    queryFn: () => openApiGet("/api/market/index-intraday", {
      query: { symbol },
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<IndexIntradayData>(),
    enabled: Boolean(symbol),
    staleTime: QUERY_CACHE_POLICIES.indexIntraday.staleMs,
    refetchInterval: isTradingSession ? QUERY_CACHE_POLICIES.indexIntraday.pollMs : false,
  });
}

export function useMarketIndexKline(symbol: string, period = "daily") {
  const startDate = oneYearAgoDate();
  return useQuery({
    queryKey: queryKeys.market.indexKline(symbol, period, startDate),
    queryFn: () => openApiGet("/api/market/index-kline", {
      query: { symbol, period, start_date: startDate },
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<KlineData>(),
    enabled: !!symbol,
    staleTime: 5 * 60 * 1000,
  });
}

export function useHsgtFlow(enabled = true, autoRefresh = true) {
  const isTradingSession = useAStockTradingSession();
  return useQuery({
    queryKey: queryKeys.market.hsgtFlow,
    queryFn: () => openApiGet("/api/market/hsgt-flow", {
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<HsgtFlow>(),
    enabled,
    staleTime: 60 * 1000,
    refetchInterval: enabled && autoRefresh && isTradingSession ? 60 * 1000 : false,
  });
}

export function useMarketMargin(enabled = true) {
  return useQuery({
    queryKey: queryKeys.market.margin,
    queryFn: () => openApiGet("/api/market/margin", {
      query: { days: 240 },
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<MarketMargin>(),
    enabled,
    staleTime: 10 * 60 * 1000,
  });
}

export function useTradingCalendar(year: number) {
  return useQuery({
    queryKey: queryKeys.market.tradingCalendar(String(year)),
    queryFn: () => openApiGet("/api/market/trading-calendar", {
      query: { start_date: `${year}-01-01`, end_date: `${year}-12-31` },
    }),
    select: asApiModel<TradingCalendar>(),
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useThsHotRank(enabled = true) {
  const isTradingSession = useAStockTradingSession();
  return useQuery({
    queryKey: queryKeys.market.thsHotRank,
    queryFn: () => openApiGet("/api/market/hot-rank/ths", {
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<ThsHotStock[]>(),
    enabled,
    staleTime: QUERY_CACHE_POLICIES.thsHotRank.staleMs,
    refetchInterval: enabled && isTradingSession ? QUERY_CACHE_POLICIES.thsHotRank.pollMs : false,
  });
}

export function useThsHotConcept(enabled = true) {
  const isTradingSession = useAStockTradingSession();
  return useQuery({
    queryKey: queryKeys.market.thsHotConcept,
    queryFn: () => openApiGet("/api/market/hot-rank/ths/concept", {
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<ThsHotPlate[]>(),
    enabled,
    staleTime: QUERY_CACHE_POLICIES.thsHotRank.staleMs,
    refetchInterval: enabled && isTradingSession ? QUERY_CACHE_POLICIES.thsHotRank.pollMs : false,
  });
}

export function useThsHotIndustry(enabled = true) {
  const isTradingSession = useAStockTradingSession();
  return useQuery({
    queryKey: queryKeys.market.thsHotIndustry,
    queryFn: () => openApiGet("/api/market/hot-rank/ths/industry", {
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<ThsHotPlate[]>(),
    enabled,
    staleTime: QUERY_CACHE_POLICIES.thsHotRank.staleMs,
    refetchInterval: enabled && isTradingSession ? QUERY_CACHE_POLICIES.thsHotRank.pollMs : false,
  });
}

export function useIndustryRankings(date: string) {
  const isTradingSession = useAStockTradingSession();
  const isCurrentDate = date === dayjs().format("YYYY-MM-DD");
  return useQuery({
    queryKey: queryKeys.market.industryRankings(date),
    queryFn: () => openApiGet("/api/market/industry-rankings", {
      query: { date },
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<IndustryRankings>(),
    enabled: Boolean(date),
    staleTime: isCurrentDate
      ? QUERY_CACHE_POLICIES.industryRankings.liveStaleMs
      : QUERY_CACHE_POLICIES.industryRankings.stableStaleMs,
    refetchInterval: isCurrentDate && isTradingSession
      ? QUERY_CACHE_POLICIES.industryRankings.pollMs
      : false,
  });
}

export function useDragonTigerList(reportDate: string) {
  return useQuery({
    queryKey: queryKeys.market.dragonTiger(reportDate),
    queryFn: () => openApiGet("/api/market/dragon-tiger", {
      query: { report_date: reportDate },
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<DragonTigerItem[]>(),
    enabled: !!reportDate,
    staleTime: 10 * 60 * 1000,
  });
}

export function useDragonTigerDetail(code: string, reportDate: string) {
  return useQuery({
    queryKey: queryKeys.market.dragonTigerDetail(code, reportDate),
    queryFn: () => openApiGet("/api/stock/{code}/dragon-tiger", {
      path: { code },
      query: { report_date: reportDate },
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<DragonTigerDetail[]>(),
    enabled: !!code && !!reportDate,
    staleTime: 10 * 60 * 1000,
  });
}

export function useMarketKuaixun() {
  return useQuery({
    queryKey: queryKeys.market.kuaixun,
    queryFn: () => openApiGet("/api/market/kuaixun", {
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<FeedNewsItem[]>(),
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
  });
}

export function useMarketOtherNews() {
  return useQuery({
    queryKey: queryKeys.market.otherNews,
    queryFn: () => openApiGet("/api/market/other-news", {
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<FeedNewsItem[]>(),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });
}

export function useMarketTwitterFeed() {
  return useQuery({
    queryKey: queryKeys.market.twitterFeed,
    queryFn: () => openApiGet("/api/market/twitter-feed", {
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<FeedNewsItem[]>(),
    staleTime: 30 * 60 * 1000,
    refetchInterval: 30 * 60 * 1000,
  });
}

export function useMarketTwitterFeedRefresh() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => openApiPost("/api/market/twitter-feed/refresh", {
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.market.twitterFeed });
      queryClient.invalidateQueries({ queryKey: queryKeys.market.twitterAnalysisRoot });
    },
  });
}

export function useMarketTwitterAnalysis(username: string) {
  return useQuery({
    queryKey: queryKeys.market.twitterAnalysis(username),
    queryFn: () => openApiGet("/api/market/twitter-analyze", {
      query: { username },
      options: { timeoutMs: API_TIMEOUTS.LONG_RUNNING },
    }),
    enabled: !!username,
    staleTime: 12 * 60 * 60 * 1000,
    gcTime: 12 * 60 * 60 * 1000,
  });
}

export function useMarketTwitterAnalysisRefresh(username: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => openApiGet("/api/market/twitter-analyze", {
      query: { username, force_refresh: true },
      options: { timeoutMs: API_TIMEOUTS.LONG_RUNNING },
    }),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.market.twitterAnalysis(username), data);
    },
  });
}

export function useNewsAnalysis() {
  return useQuery({
    queryKey: queryKeys.market.newsAnalysis,
    queryFn: () => openApiGet("/api/market/news-analysis", {
      options: { timeoutMs: API_TIMEOUTS.LONG_RUNNING },
    }),
    select: asApiModel<NewsAnalysis>(),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });
}

export function useMacroAllData() {
  return useQuery({
    queryKey: queryKeys.market.macroAll,
    queryFn: () => openApiGet("/api/macro/all", {
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<MacroAllData>(),
    staleTime: 5 * 60 * 1000,
  });
}

export function useForceRefreshMacroAllData() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => openApiGet("/api/macro/all", {
      query: { force_refresh: true },
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }).then(asApiModel<MacroAllData>()),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.market.macroAll, data);
    },
  });
}


export function useUsMacroData() {
  return useQuery({
    queryKey: queryKeys.market.macroUs,
    queryFn: () => openApiGet("/api/macro/us", {
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<MacroUsData>(),
    staleTime: 5 * 60 * 1000,
  });
}
