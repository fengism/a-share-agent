import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { API_TIMEOUTS, apiGet, apiPost } from "../client";
import type { components } from "../generated/schema";
import { queryKeys } from "../queryKeys";
import { oneYearAgoDate } from "../../utils/date";
import type {
  DragonTigerDetail,
  DragonTigerItem,
  FeedNewsItem,
  HsgtFlow,
  IndustryRankings,
  KlineData,
  MacroAllData,
  MarketIndices,
  NewsAnalysis,
  ThsHotPlate,
  ThsHotStock,
} from "../../types/stock";

type TwitterAnalysisResult = components["schemas"]["TwitterAnalysisResult"];

export function useMarketIndices() {
  return useQuery({
    queryKey: queryKeys.market.indices,
    queryFn: ({ signal }) => apiGet<MarketIndices>("/market/indices", undefined, { signal }),
    staleTime: 5 * 60 * 1000,
  });
}

export function useMarketIndexKline(symbol: string, period = "daily") {
  const startDate = oneYearAgoDate();

  return useQuery({
    queryKey: queryKeys.market.indexKline(symbol, period, startDate),
    queryFn: ({ signal }) =>
      apiGet<KlineData>("/market/index-kline", {
        symbol,
        period,
        start_date: startDate,
      }, { signal }),
    enabled: !!symbol,
    staleTime: 5 * 60 * 1000,
  });
}

export function useHsgtFlow(enabled = true, autoRefresh = true) {
  return useQuery({
    queryKey: queryKeys.market.hsgtFlow,
    queryFn: ({ signal }) => apiGet<HsgtFlow>("/market/hsgt-flow", undefined, { signal }),
    enabled,
    staleTime: 60 * 1000,
    refetchInterval: enabled && autoRefresh ? 60 * 1000 : false,
  });
}

export function useThsHotRank(enabled = true) {
  return useQuery({
    queryKey: queryKeys.market.thsHotRank,
    queryFn: ({ signal }) => apiGet<ThsHotStock[]>("/market/hot-rank/ths", undefined, { signal }),
    enabled,
    staleTime: 60 * 1000,
    refetchInterval: enabled ? 60 * 1000 : false,
  });
}

export function useThsHotConcept(enabled = true) {
  return useQuery({
    queryKey: queryKeys.market.thsHotConcept,
    queryFn: ({ signal }) => apiGet<ThsHotPlate[]>("/market/hot-rank/ths/concept", undefined, { signal }),
    enabled,
    staleTime: 60 * 1000,
    refetchInterval: enabled ? 60 * 1000 : false,
  });
}

export function useThsHotIndustry(enabled = true) {
  return useQuery({
    queryKey: queryKeys.market.thsHotIndustry,
    queryFn: ({ signal }) => apiGet<ThsHotPlate[]>("/market/hot-rank/ths/industry", undefined, { signal }),
    enabled,
    staleTime: 60 * 1000,
    refetchInterval: enabled ? 60 * 1000 : false,
  });
}

export function useIndustryRankings() {
  return useQuery({
    queryKey: queryKeys.market.industryRankings,
    queryFn: ({ signal }) => apiGet<IndustryRankings>("/market/industry-rankings", undefined, { signal }),
    staleTime: 5 * 60 * 1000,
  });
}

export function useDragonTigerList(reportDate: string) {
  return useQuery({
    queryKey: queryKeys.market.dragonTiger(reportDate),
    queryFn: ({ signal }) => apiGet<DragonTigerItem[]>("/market/dragon-tiger", { report_date: reportDate }, { signal }),
    enabled: !!reportDate,
    staleTime: 10 * 60 * 1000,
  });
}

export function useDragonTigerDetail(code: string, reportDate: string) {
  return useQuery({
    queryKey: queryKeys.market.dragonTigerDetail(code, reportDate),
    queryFn: ({ signal }) => apiGet<DragonTigerDetail[]>(`/stock/${code}/dragon-tiger`, { report_date: reportDate }, { signal }),
    enabled: !!code && !!reportDate,
    staleTime: 10 * 60 * 1000,
  });
}

export function useMarketKuaixun() {
  return useQuery({
    queryKey: queryKeys.market.kuaixun,
    queryFn: ({ signal }) => apiGet<FeedNewsItem[]>("/market/kuaixun", undefined, { signal }),
    staleTime: 60 * 1000,
    refetchInterval: 60 * 1000,
  });
}

export function useMarketOtherNews() {
  return useQuery({
    queryKey: queryKeys.market.otherNews,
    queryFn: ({ signal }) => apiGet<FeedNewsItem[]>("/market/other-news", undefined, { signal }),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });
}

export function useMarketTwitterFeed() {
  return useQuery({
    queryKey: queryKeys.market.twitterFeed,
    queryFn: ({ signal }) => apiGet<FeedNewsItem[]>("/market/twitter-feed", undefined, { signal }),
    staleTime: 30 * 60 * 1000,
    refetchInterval: 30 * 60 * 1000,
  });
}

export function useMarketTwitterFeedRefresh() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost("/market/twitter-feed/refresh", undefined, { timeoutMs: API_TIMEOUTS.EXTERNAL }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.market.twitterFeed });
      queryClient.invalidateQueries({ queryKey: queryKeys.market.twitterAnalysisRoot });
    },
  });
}

export function useMarketTwitterAnalysis(username: string) {
  return useQuery({
    queryKey: queryKeys.market.twitterAnalysis(username),
    queryFn: ({ signal }) => apiGet<TwitterAnalysisResult>("/market/twitter-analyze", { username }, {
      signal,
      timeoutMs: API_TIMEOUTS.LONG_RUNNING,
    }),
    enabled: !!username,
    staleTime: 12 * 60 * 60 * 1000,
    gcTime: 12 * 60 * 60 * 1000,
  });
}

export function useMarketTwitterAnalysisRefresh(username: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiGet<TwitterAnalysisResult>("/market/twitter-analyze", {
      username,
      force_refresh: true,
    }, { timeoutMs: API_TIMEOUTS.LONG_RUNNING }),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.market.twitterAnalysis(username), data);
    },
  });
}

export function useNewsAnalysis() {
  return useQuery({
    queryKey: queryKeys.market.newsAnalysis,
    queryFn: ({ signal }) => apiGet<NewsAnalysis>("/market/news-analysis", undefined, {
      signal,
      timeoutMs: API_TIMEOUTS.LONG_RUNNING,
    }),
    staleTime: 5 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  });
}

export function useMacroAllData() {
  return useQuery({
    queryKey: queryKeys.market.macroAll,
    queryFn: ({ signal }) => apiGet<MacroAllData>("/macro/all", undefined, { signal }),
    staleTime: 5 * 60 * 1000,
  });
}

export function useForceRefreshMacroAllData() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiGet<MacroAllData>(
      "/macro/all",
      { force_refresh: true },
      { timeoutMs: API_TIMEOUTS.EXTERNAL },
    ),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.market.macroAll, data);
    },
  });
}
