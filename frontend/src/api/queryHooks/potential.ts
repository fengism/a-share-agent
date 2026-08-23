import { useMutation, useQuery } from "@tanstack/react-query";
import { apiGet, apiPost } from "../client";
import { queryKeys } from "../queryKeys";
import type { PotentialDailyResult, PotentialDateItem } from "../../types/stock";

export function usePotentialDaily(date: string | null) {
  return useQuery({
    queryKey: date ? queryKeys.potential.byDate(date) : queryKeys.potential.latest,
    queryFn: () => apiGet<PotentialDailyResult | null>(
      "/potential/latest",
      date ? { date } : undefined,
    ),
    staleTime: 10 * 60 * 1000,
  });
}

export function usePotentialDates() {
  return useQuery({
    queryKey: queryKeys.potential.dates,
    queryFn: () => apiGet<PotentialDateItem[]>("/potential/dates"),
    staleTime: 10 * 60 * 1000,
  });
}

export function usePotentialRun() {
  return useMutation({
    mutationFn: (force: boolean) => apiPost<PotentialDailyResult | null>(
      force ? "/potential/run?force=true" : "/potential/run",
      {},
    ),
  });
}
