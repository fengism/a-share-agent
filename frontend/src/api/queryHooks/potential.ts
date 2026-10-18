import { useMutation, useQuery } from "@tanstack/react-query";
import { API_TIMEOUTS, apiGet, apiPost } from "../client";
import { QUERY_CACHE_POLICIES } from "../cachePolicies";
import { queryKeys } from "../queryKeys";
import type {
  PotentialDailyResult,
  PotentialDateItem,
  PotentialPerformanceSummary,
  PotentialRunStatus,
} from "../../types/stock";

export function usePotentialDaily(date: string | null) {
  return useQuery({
    queryKey: date ? queryKeys.potential.byDate(date) : queryKeys.potential.latest,
    queryFn: () => apiGet<PotentialDailyResult | null>(
      "/potential/latest",
      date ? { date } : undefined,
    ),
    staleTime: QUERY_CACHE_POLICIES.potentialResults.staleMs,
  });
}

export function usePotentialDates() {
  return useQuery({
    queryKey: queryKeys.potential.dates,
    queryFn: () => apiGet<PotentialDateItem[]>("/potential/dates"),
    staleTime: QUERY_CACHE_POLICIES.potentialResults.staleMs,
  });
}

export function usePotentialPerformance(date: string | null, days: number) {
  return useQuery({
    queryKey: date ? queryKeys.potential.performance(date, days) : ["potentialPerformance", "none", days],
    queryFn: () => date
      ? apiGet<PotentialPerformanceSummary | null>("/potential/performance", { date, days })
      : Promise.resolve(null),
    enabled: Boolean(date),
    staleTime: 60_000,
  });
}

export function usePotentialRun() {
  return useMutation({
    mutationFn: (force: boolean) => apiPost<PotentialRunStatus>(
      force ? "/potential/run?force=true" : "/potential/run",
      {},
      { timeoutMs: API_TIMEOUTS.DEFAULT },
    ),
  });
}

export function usePotentialRunStatus(enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.potential.runStatus,
    queryFn: () => apiGet<PotentialRunStatus>("/potential/run/status"),
    enabled,
    staleTime: 0,
    refetchInterval: (query) => (query.state.data?.running ? 5_000 : false),
  });
}
