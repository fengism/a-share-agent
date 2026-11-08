import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

export interface LeekSubScores {
  flow: number;
  guba: number;
  crowd: number;
  trap: number;
}

export interface CrowdedStockItem {
  code: string;
  name: string;
  rank?: number;
  change_pct?: number;
  reason?: string;
}

export interface IndustryLeekItem {
  industry_name: string;
  leek_score: number;
  risk_level: "safe" | "normal" | "fever" | "extreme";
  sub_scores: LeekSubScores;
  change_pct: number;
  main_net: number;
  retail_net: number;
  crowded_stocks: CrowdedStockItem[];
  warning_signals: string[];
}

export interface MarketLeekSummary {
  median_score: number;
  extreme_count: number;
  fever_count: number;
  safe_count: number;
  market_sentiment_label: string;
}

export interface LeekIndexOverviewResponse {
  trade_date: string;
  updated_at: string;
  summary: MarketLeekSummary;
  industries: IndustryLeekItem[];
}

export interface LeekHistoryPoint {
  date: string;
  score: number;
  risk_level: "safe" | "normal" | "fever" | "extreme";
  sub_scores: LeekSubScores;
  industry_change_pct?: number;
}

export interface LeekIndexHistoryResponse {
  industry_name: string;
  history: LeekHistoryPoint[];
}

export function useLeekIndexOverview(forceRefresh = false) {
  return useQuery<LeekIndexOverviewResponse>({
    queryKey: ["sentiment", "leek-index", "overview", forceRefresh],
    queryFn: async () => {
      const url = `/api/sentiment/leek-index/overview${forceRefresh ? "?force_refresh=true" : ""}`;
      const res = await fetch(url);
      if (!res.ok) {
        throw new Error(`获取行业韭菜指数失败: ${res.statusText}`);
      }
      return res.json();
    },
    staleTime: 60 * 1000,
  });
}

export function useIndustryLeekHistory(industryName: string, days = 30) {
  return useQuery<LeekIndexHistoryResponse>({
    queryKey: ["sentiment", "leek-index", "history", industryName, days],
    queryFn: async () => {
      const res = await fetch(
        `/api/sentiment/leek-index/${encodeURIComponent(industryName)}/history?days=${days}`
      );
      if (!res.ok) {
        throw new Error(`获取 ${industryName} 历史韭菜指数失败: ${res.statusText}`);
      }
      return res.json();
    },
    enabled: Boolean(industryName),
    staleTime: 5 * 60 * 1000,
  });
}

export function useRefreshLeekIndex() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await fetch("/api/sentiment/leek-index/refresh", {
        method: "POST",
      });
      if (!res.ok) {
        throw new Error(`刷新韭菜指数失败: ${res.statusText}`);
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sentiment", "leek-index"] });
    },
  });
}
