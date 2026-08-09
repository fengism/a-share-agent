import { useMutation, useQuery } from "@tanstack/react-query";
import { apiGet, apiPost } from "../client";
import { queryKeys } from "../queryKeys";
import type {
  ScreenerFilter,
  ScreenerResult,
  ValuationPercentileRequest,
  ValuationPercentileResult,
} from "../../types/stock";

export function useScreenerScreen(filters: ScreenerFilter, enabled = true) {
  return useQuery({
    queryKey: queryKeys.screener.screen(filters),
    queryFn: ({ signal }) => apiPost<ScreenerResult>("/screener/screen", filters, { signal }),
    enabled,
    staleTime: 2 * 60 * 1000,
    placeholderData: (previous) => previous,
  });
}

export function useIndustries() {
  return useQuery({
    queryKey: queryKeys.screener.industries,
    queryFn: ({ signal }) => apiGet<string[]>("/screener/industries", undefined, { signal }),
    staleTime: 24 * 60 * 60 * 1000,
  });
}

export function useComputePercentiles() {
  return useMutation({
    mutationFn: (req: ValuationPercentileRequest) =>
      apiPost<ValuationPercentileResult>("/screener/percentile", req),
  });
}
