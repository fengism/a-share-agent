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
  NorthboundHistory,
  MarketPriceAnomaly,
  MarketPriceAnomalyCount,
  MarketSectorStocksHistory,
  MarketWind,
  MarketWindStocks,
  MacroAllData,
  MacroUsData,
  GlobalMacroRatesData,
  TreasuryYieldsResponse,
  CommoditiesResponse,
  CustomsTradeDataResponse,
  MarketIndices,
  NewsAnalysis,
  SgeGoldResponse,
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
    staleTime: QUERY_CACHE_POLICIES.marketRealtime.staleMs,
    refetchInterval: isTradingSession ? QUERY_CACHE_POLICIES.marketRealtime.pollMs : false,
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
    staleTime: QUERY_CACHE_POLICIES.marketRealtime.staleMs,
    refetchInterval: isTradingSession ? QUERY_CACHE_POLICIES.marketRealtime.pollMs : false,
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
    staleTime: QUERY_CACHE_POLICIES.marketRealtime.staleMs,
    refetchInterval: isTradingSession ? QUERY_CACHE_POLICIES.marketRealtime.pollMs : false,
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
    staleTime: QUERY_CACHE_POLICIES.marketMainline.staleMs,
    refetchInterval: isTradingSession
      ? QUERY_CACHE_POLICIES.marketMainline.activePollMs
      : QUERY_CACHE_POLICIES.marketMainline.idlePollMs,
    refetchOnMount: "always",
    refetchOnWindowFocus: true,
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
    staleTime: QUERY_CACHE_POLICIES.marketRealtime.staleMs,
    refetchInterval: isTradingSession ? QUERY_CACHE_POLICIES.marketRealtime.pollMs : false,
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
    staleTime: QUERY_CACHE_POLICIES.marketMinute.staleMs,
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
    staleTime: QUERY_CACHE_POLICIES.marketRealtime.staleMs,
    refetchInterval: enabled && autoRefresh && isTradingSession
      ? QUERY_CACHE_POLICIES.marketRealtime.pollMs
      : false,
  });
}

export function useNorthboundHistory(pageSize = 500) {
  return useQuery({
    queryKey: queryKeys.market.northboundHistory(pageSize),
    queryFn: () => openApiGet("/api/market/northbound-history", {
      query: { page_size: pageSize },
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<NorthboundHistory>(),
    staleTime: QUERY_CACHE_POLICIES.marketTenMinutes.staleMs,
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
    staleTime: QUERY_CACHE_POLICIES.marketTenMinutes.staleMs,
  });
}

export function useMarketPriceAnomaly(pageNo = 1, pageSize = 200, enabled = true) {
  return useQuery({
    queryKey: queryKeys.market.priceAnomaly(pageNo, pageSize),
    queryFn: () => openApiGet("/api/market/price-anomaly", {
      query: { page_no: pageNo, page_size: pageSize },
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<MarketPriceAnomaly>(),
    enabled,
    staleTime: QUERY_CACHE_POLICIES.priceAnomaly.staleMs,
  });
}

export function useMarketPriceAnomalyCount(
  pageNo = 1,
  pageSize = 50,
  sortKey = "",
  sortDir = "",
  enabled = true,
) {
  return useQuery({
    queryKey: queryKeys.market.priceAnomalyCount(pageNo, pageSize, sortKey, sortDir),
    queryFn: () => openApiGet("/api/market/price-anomaly/count", {
      query: {
        page_no: pageNo,
        page_size: pageSize,
        sort_key: sortKey,
        sort_dir: sortDir,
      },
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<MarketPriceAnomalyCount>(),
    enabled,
    staleTime: QUERY_CACHE_POLICIES.priceAnomaly.staleMs,
  });
}

export function useTradingCalendar(year: number) {
  return useQuery({
    queryKey: queryKeys.market.tradingCalendar(String(year)),
    queryFn: () => openApiGet("/api/market/trading-calendar", {
      query: { start_date: `${year}-01-01`, end_date: `${year}-12-31` },
    }),
    select: asApiModel<TradingCalendar>(),
    staleTime: QUERY_CACHE_POLICIES.immutableHistory.staleMs,
  });
}

/**
 * 今天是否为 A 股交易日。
 *
 * 周末直接判定为非交易日（无需等待日历返回）；工作日依赖后端交易日历，
 * 日历未加载或失败时返回 null（未知），由调用方自行放行以免误隐藏数据。
 */
export function useIsTradingDay(): boolean | null {
  const now = new Date();
  const isWeekend = now.getDay() === 0 || now.getDay() === 6;
  const calendarQuery = useTradingCalendar(now.getFullYear());
  if (isWeekend) return false;
  const calendar = calendarQuery.data;
  return calendar ? calendar.today_is_trading_day : null;
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
  const isHistorical = reportDate < dayjs().format("YYYY-MM-DD");
  return useQuery({
    queryKey: queryKeys.market.dragonTiger(reportDate),
    queryFn: () => openApiGet("/api/market/dragon-tiger", {
      query: { report_date: reportDate },
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<DragonTigerItem[]>(),
    enabled: !!reportDate,
    staleTime: isHistorical
      ? QUERY_CACHE_POLICIES.immutableHistory.staleMs
      : QUERY_CACHE_POLICIES.marketTenMinutes.staleMs,
  });
}

export function useDragonTigerDetail(code: string, reportDate: string) {
  const isHistorical = reportDate < dayjs().format("YYYY-MM-DD");
  return useQuery({
    queryKey: queryKeys.market.dragonTigerDetail(code, reportDate),
    queryFn: () => openApiGet("/api/stock/{code}/dragon-tiger", {
      path: { code },
      query: { report_date: reportDate },
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<DragonTigerDetail[]>(),
    enabled: !!code && !!reportDate,
    staleTime: isHistorical
      ? QUERY_CACHE_POLICIES.immutableHistory.staleMs
      : QUERY_CACHE_POLICIES.marketTenMinutes.staleMs,
  });
}

export function useMarketKuaixun() {
  return useQuery({
    queryKey: queryKeys.market.kuaixun,
    queryFn: () => openApiGet("/api/market/kuaixun", {
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<FeedNewsItem[]>(),
    staleTime: QUERY_CACHE_POLICIES.marketRealtime.staleMs,
    refetchInterval: QUERY_CACHE_POLICIES.marketRealtime.pollMs,
  });
}

export function useMarketOtherNews() {
  return useQuery({
    queryKey: queryKeys.market.otherNews,
    queryFn: () => openApiGet("/api/market/other-news", {
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<FeedNewsItem[]>(),
    staleTime: QUERY_CACHE_POLICIES.marketMinute.staleMs,
    refetchInterval: QUERY_CACHE_POLICIES.marketMinute.pollMs,
  });
}

export function useMarketTwitterFeed() {
  return useQuery({
    queryKey: queryKeys.market.twitterFeed,
    queryFn: () => openApiGet("/api/market/twitter-feed", {
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<FeedNewsItem[]>(),
    staleTime: QUERY_CACHE_POLICIES.socialFeed.staleMs,
    refetchInterval: QUERY_CACHE_POLICIES.socialFeed.pollMs,
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
    staleTime: QUERY_CACHE_POLICIES.socialAnalysis.staleMs,
    gcTime: QUERY_CACHE_POLICIES.socialAnalysis.gcMs,
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
    staleTime: QUERY_CACHE_POLICIES.marketMinute.staleMs,
    refetchInterval: QUERY_CACHE_POLICIES.marketMinute.pollMs,
  });
}

export function useMacroAllData() {
  return useQuery({
    queryKey: queryKeys.market.macroAll,
    queryFn: () => openApiGet("/api/macro/all", {
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<MacroAllData>(),
    staleTime: QUERY_CACHE_POLICIES.macro.staleMs,
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
    staleTime: QUERY_CACHE_POLICIES.macro.staleMs,
  });
}

export function useGlobalMacroRates() {
  return useQuery({
    queryKey: queryKeys.market.macroGlobalRates,
    queryFn: () => openApiGet("/api/macro/global-rates", {
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<GlobalMacroRatesData>(),
    staleTime: QUERY_CACHE_POLICIES.marketRealtime.staleMs,
  });
}

export function useCommoditySpotPrices(symbol = "") {
  return useQuery({
    queryKey: queryKeys.market.macroCommodities(symbol),
    queryFn: () => openApiGet("/api/macro/commodities", {
      query: symbol ? { symbol } : undefined,
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<CommoditiesResponse>(),
    staleTime: QUERY_CACHE_POLICIES.marketRealtime.staleMs,
  });
}

export function useSgeGoldHistory(symbol = "Au99.99") {
  return useQuery({
    queryKey: queryKeys.market.macroSgeGold(symbol),
    queryFn: () => openApiGet("/api/macro/sge-gold", {
      query: { symbol },
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<SgeGoldResponse>(),
    staleTime: QUERY_CACHE_POLICIES.macro.staleMs,
  });
}

export function useCustomsTradeData(commodity = "") {
  return useQuery({
    queryKey: queryKeys.market.macroCustomsTrade(commodity),
    queryFn: () => openApiGet("/api/macro/customs-trade", {
      query: commodity ? { commodity } : undefined,
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<CustomsTradeDataResponse>(),
    staleTime: QUERY_CACHE_POLICIES.macro.staleMs,
  });
}

export function useTreasuryYieldCurve(pageSize = 300) {
  return useQuery({
    queryKey: queryKeys.market.macroTreasuryYields(pageSize),
    queryFn: () => openApiGet("/api/macro/treasury-yields", {
      query: { page_size: pageSize },
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }),
    select: asApiModel<TreasuryYieldsResponse>(),
    staleTime: QUERY_CACHE_POLICIES.macro.staleMs,
  });
}
