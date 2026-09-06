import { useMutation, useQuery } from "@tanstack/react-query";
import { apiGet, apiPost } from "../client";
import { QUERY_CACHE_POLICIES } from "../cachePolicies";
import { streamScreenerStrategy, type ScreenerStrategyProgress } from "../sse";
import { queryKeys } from "../queryKeys";
import type {
  ScreenerFilter,
  ScreenerItem,
  ScreenerResult,
  ScreenerStrategyPreset,
  ScreenerStrategyRequest,
  ScreenerStrategyResult,
  ValuationPercentileRequest,
  ValuationPercentileResult,
} from "../../types/stock";

function normalizeScreenerCode(value: string): string {
  const trimmed = value.trim();
  const withoutMarket = /^(sh|sz|bj)/i.test(trimmed) ? trimmed.slice(2) : trimmed;
  return /^\d+$/.test(withoutMarket) ? withoutMarket.padStart(6, "0") : withoutMarket;
}

function deduplicateScreenerItems(items: ScreenerItem[]): ScreenerItem[] {
  const unique = new Map<string, ScreenerItem>();
  for (const item of items) {
    const code = normalizeScreenerCode(item.code);
    if (!code || unique.has(code)) continue;
    unique.set(code, { ...item, code });
  }
  return [...unique.values()];
}

function normalizeScreenerResult(result: ScreenerResult): ScreenerResult {
  const items = deduplicateScreenerItems(result.items);
  return {
    ...result,
    items,
    total: Math.max(0, result.total - (result.items.length - items.length)),
  };
}

export function useScreenerScreen(filters: ScreenerFilter, enabled = true) {
  return useQuery({
    queryKey: queryKeys.screener.screen(filters),
    queryFn: async () => normalizeScreenerResult(
      await apiPost<ScreenerResult>("/screener/screen", filters),
    ),
    enabled,
    staleTime: QUERY_CACHE_POLICIES.screenerResults.staleMs,
    placeholderData: (previous) => previous,
  });
}

export function useIndustries() {
  return useQuery({
    queryKey: queryKeys.screener.industries,
    queryFn: () => apiGet<string[]>("/screener/industries"),
    staleTime: QUERY_CACHE_POLICIES.reference.staleMs,
  });
}

export function useScreenerConcepts() {
  return useQuery({
    queryKey: queryKeys.screener.concepts,
    queryFn: () => apiGet<string[]>("/screener/concepts"),
    staleTime: QUERY_CACHE_POLICIES.reference.staleMs,
  });
}

export function useComputePercentiles() {
  return useMutation({
    mutationFn: (req: ValuationPercentileRequest) =>
      apiPost<ValuationPercentileResult>("/screener/percentile", req),
  });
}


export function useScreenerStrategies() {
  return useQuery({
    queryKey: queryKeys.screener.strategies,
    queryFn: () => apiGet<ScreenerStrategyPreset[]>("/screener/strategies"),
    staleTime: QUERY_CACHE_POLICIES.reference.staleMs,
  });
}

export type ScreenerStrategyExecutionRequest = ScreenerStrategyRequest & {
  candidate_filters?: ScreenerFilter;
  candidate_items?: ScreenerItem[];
  scan_limit?: 50 | 200;
  onProgress?: (event: ScreenerStrategyProgress) => void;
  onStarted?: (cancel: () => void) => void;
};

export type ScreenerStrategyExecutionResult = ScreenerStrategyResult & {
  matched_items: ScreenerItem[];
};

export function useRunScreenerStrategy() {
  return useMutation({
    mutationFn: async (request: ScreenerStrategyExecutionRequest) => {
      const candidateController = new AbortController();
      let cancelRequested = false;
      const cancellation: { stream?: () => Promise<unknown> } = {};
      const cancel = () => {
        if (cancelRequested) return;
        cancelRequested = true;
        candidateController.abort();
        void cancellation.stream?.();
      };
      request.onStarted?.(cancel);

      let codes = request.codes;
      let candidateItems = deduplicateScreenerItems(request.candidate_items ?? []);
      if (request.scan_limit === 200 && request.candidate_filters) {
        let candidates: ScreenerResult;
        try {
          candidates = await apiPost<ScreenerResult>("/screener/screen", {
            ...request.candidate_filters,
            page: 1,
            page_size: 200,
          }, { signal: candidateController.signal });
        } catch (error) {
          if (cancelRequested) throw new Error("已取消");
          throw error;
        }
        candidateItems = deduplicateScreenerItems(candidates.items);
        codes = candidateItems.map((item) => item.code);
      }
      if (cancelRequested) throw new Error("已取消");
      codes = [...new Set(codes.map(normalizeScreenerCode).filter(Boolean))];
      if (codes.length === 0) {
        throw new Error("当前筛选条件下没有可执行策略的候选股票");
      }
      const stream = streamScreenerStrategy({
        strategy_key: request.strategy_key,
        version: request.version,
        parameters: request.parameters,
        lookback_days: request.lookback_days,
        max_signal_age_bars: request.max_signal_age_bars,
        codes,
      }, request.onProgress ?? (() => undefined));
      cancellation.stream = stream.cancel;
      if (cancelRequested) {
        void stream.cancel();
        throw new Error("已取消");
      }
      const result = await stream.promise;
      const matchedCodes = new Set(result.matched_codes.map(normalizeScreenerCode));
      return {
        ...result,
        matched_items: candidateItems.filter((item) => matchedCodes.has(item.code)),
      } satisfies ScreenerStrategyExecutionResult;
    },
  });
}
