import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiDelete, apiGet, apiPost } from "../client";
import type { components } from "../generated/schema";
import { queryKeys } from "../queryKeys";

export type QuantBacktestCreate = components["schemas"]["QuantBacktestCreate"];
export type QuantBacktestRun = components["schemas"]["QuantBacktestRun"];
export type QuantBacktestResult = components["schemas"]["QuantBacktestResult"];
export type QuantStrategyPreset = components["schemas"]["QuantStrategyPreset"];
export type QuantSavedStrategy = components["schemas"]["QuantSavedStrategy"];
export type QuantStrategyConfig = components["schemas"]["QuantStrategyConfig"];

const isActive = (status?: string) => status === "pending" || status === "running";

export function useQuantStrategyPresets() {
  return useQuery({
    queryKey: queryKeys.quant.presets,
    queryFn: ({ signal }) => apiGet<QuantStrategyPreset[]>("/quant/strategy-presets", undefined, { signal }),
    staleTime: Infinity,
  });
}

export function useSavedQuantStrategies() {
  return useQuery({
    queryKey: queryKeys.quant.strategies,
    queryFn: ({ signal }) => apiGet<QuantSavedStrategy[]>("/quant/strategies", undefined, { signal }),
  });
}

export function useSaveQuantStrategy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: { name: string; config: QuantStrategyConfig }) => (
      apiPost<QuantSavedStrategy>("/quant/strategies", request)
    ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.quant.strategies }),
  });
}

export function useDeleteQuantStrategy() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (strategyId: number) => apiDelete<components["schemas"]["QuantDeleteResponse"]>(
      `/quant/strategies/${strategyId}`,
    ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.quant.strategies }),
  });
}

export function useQuantBacktests() {
  return useQuery({
    queryKey: queryKeys.quant.runs,
    queryFn: ({ signal }) => apiGet<components["schemas"]["QuantBacktestList"]>(
      "/quant/backtests",
      undefined,
      { signal },
    ),
    refetchInterval: (query) => query.state.data?.items.some((run) => isActive(run.status)) ? 1_000 : false,
  });
}

export function useQuantBacktest(runId?: string) {
  return useQuery({
    queryKey: queryKeys.quant.run(runId ?? ""),
    queryFn: ({ signal }) => apiGet<QuantBacktestRun>(`/quant/backtests/${runId}`, undefined, { signal }),
    enabled: Boolean(runId),
    refetchInterval: (query) => isActive(query.state.data?.status) ? 1_000 : false,
  });
}

function useRunMutation(
  mutationFn: (runId: string) => Promise<unknown>,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: (_, runId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.quant.runs });
      queryClient.invalidateQueries({ queryKey: queryKeys.quant.run(runId) });
    },
  });
}

export function useCreateQuantBacktest() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: QuantBacktestCreate) => apiPost<QuantBacktestRun>("/quant/backtests", request),
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.quant.runs });
      queryClient.setQueryData(queryKeys.quant.run(run.id), run);
    },
  });
}

export function useCancelQuantBacktest() {
  return useRunMutation((runId) => apiPost<QuantBacktestRun>(`/quant/backtests/${runId}/cancel`));
}

export function useRetryQuantBacktest() {
  return useRunMutation((runId) => apiPost<QuantBacktestRun>(`/quant/backtests/${runId}/retry`));
}

export function useDeleteQuantBacktest() {
  return useRunMutation((runId) => apiDelete<components["schemas"]["QuantDeleteResponse"]>(
    `/quant/backtests/${runId}`,
  ));
}
