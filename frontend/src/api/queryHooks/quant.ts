import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { API_TIMEOUTS, apiDelete, apiGet, apiPost, apiPut } from "../client";
import { QUERY_CACHE_POLICIES } from "../cachePolicies";
import type { components } from "../generated/schema";
import { queryKeys } from "../queryKeys";

export type QuantBacktestCreate = components["schemas"]["QuantBacktestCreate"];
export type QuantBacktestRun = components["schemas"]["QuantBacktestRun"];
export type QuantBacktestResult = components["schemas"]["QuantBacktestResult"];
export type QuantEquityPoint = components["schemas"]["QuantEquityPoint"];
export type QuantStrategyPreset = components["schemas"]["QuantStrategyPreset"];
export type QuantSavedStrategy = components["schemas"]["QuantSavedStrategy"];
export type QuantStrategyConfig = components["schemas"]["QuantStrategyConfig"];
export type QuantStrategyDraft = components["schemas"]["QuantStrategyDraft"];
export type QuantStrategyDraftBacktestRequest = components["schemas"]["QuantStrategyDraftBacktestRequest"];
export type QuantStrategyDraftUpdateRequest = components["schemas"]["QuantStrategyDraftUpdateRequest"];
export type QuantStrategyDefinitionInput = components["schemas"]["StrategyDefinition-Input"];
export type QuantStrategyRegistryStatus = components["schemas"]["QuantStrategyRegistryStatus"];
export type QuantParameterScanRequest = components["schemas"]["QuantParameterScanRequest"];
export type QuantParameterScanPoint = components["schemas"]["QuantParameterScanPoint"];
export type QuantParameterScanResult = components["schemas"]["QuantParameterScanResult"];
type DeleteResponse = components["schemas"]["DeleteResponse"];

const isActive = (status?: string) => status === "pending" || status === "running";

export function useQuantStrategyPresets() {
  return useQuery({
    queryKey: queryKeys.quant.presets,
    queryFn: () => apiGet<QuantStrategyPreset[]>("/quant/strategy-presets"),
    staleTime: QUERY_CACHE_POLICIES.quantPresets.staleMs,
    refetchInterval: QUERY_CACHE_POLICIES.quantPresets.pollMs,
    refetchIntervalInBackground: false,
  });
}

/** 策略注册表状态（管理员接口）；非管理员传 `enabled=false` 以避免无意义的 403。 */
export function useQuantStrategyRegistryStatus(enabled = true) {
  return useQuery({
    queryKey: queryKeys.quant.registry,
    queryFn: () => apiGet<QuantStrategyRegistryStatus>("/quant/strategy-registry"),
    enabled,
  });
}

export function useQuantStrategyDrafts() {
  return useQuery({
    queryKey: queryKeys.quant.drafts,
    queryFn: () => apiGet<QuantStrategyDraft[]>("/quant/strategy-drafts"),
    refetchInterval: (query) => (
      query.state.data?.some((draft) => draft.status === "testing")
        ? QUERY_CACHE_POLICIES.quantDrafts.activePollMs
        : false
    ),
  });
}

async function cacheQuantStrategyDraft(
  queryClient: ReturnType<typeof useQueryClient>,
  draft: QuantStrategyDraft,
) {
  await queryClient.cancelQueries({ queryKey: queryKeys.quant.drafts });
  queryClient.setQueryData<QuantStrategyDraft[]>(queryKeys.quant.drafts, (drafts = []) => [
    draft,
    ...drafts.filter((item) => item.id !== draft.id),
  ]);
}

function invalidateQuantDrafts(queryClient: ReturnType<typeof useQueryClient>) {
  queryClient.invalidateQueries({ queryKey: queryKeys.quant.drafts });
}

export function useGenerateQuantStrategyDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (prompt: string) => apiPost<QuantStrategyDraft>(
      "/quant/strategy-drafts/generate",
      { prompt },
      { timeoutMs: API_TIMEOUTS.LONG_RUNNING },
    ),
    onSuccess: (draft) => cacheQuantStrategyDraft(queryClient, draft),
  });
}

export function useUpdateQuantStrategyDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ draftId, expectedDefinitionHash, definition }: {
      draftId: string;
      expectedDefinitionHash: string;
      definition: QuantStrategyDefinitionInput;
    }) => apiPut<QuantStrategyDraft>(`/quant/strategy-drafts/${draftId}`, {
      definition,
      expected_definition_hash: expectedDefinitionHash,
    }),
    onSuccess: (draft) => cacheQuantStrategyDraft(queryClient, draft),
  });
}

export function useValidateQuantStrategyDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (draftId: string) => apiPost<QuantStrategyDraft>(
      `/quant/strategy-drafts/${draftId}/validate`,
    ),
    onSuccess: (draft) => cacheQuantStrategyDraft(queryClient, draft),
  });
}

export function useBacktestQuantStrategyDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ draftId, request }: {
      draftId: string;
      request: QuantStrategyDraftBacktestRequest;
    }) => apiPost<QuantBacktestRun>(`/quant/strategy-drafts/${draftId}/backtest`, request),
    onSuccess: (run) => {
      invalidateQuantDrafts(queryClient);
      queryClient.invalidateQueries({ queryKey: queryKeys.quant.runs });
      queryClient.setQueryData(queryKeys.quant.run(run.id), run);
    },
  });
}

export function usePublishQuantStrategyDraft() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ draftId, expectedDefinitionHash }: {
      draftId: string;
      expectedDefinitionHash: string;
    }) => apiPost<QuantStrategyDraft>(`/quant/strategy-drafts/${draftId}/publish`, {
      expected_definition_hash: expectedDefinitionHash,
    }),
    onSuccess: async (draft) => {
      await cacheQuantStrategyDraft(queryClient, draft);
      queryClient.invalidateQueries({ queryKey: queryKeys.quant.registry });
      queryClient.invalidateQueries({ queryKey: queryKeys.quant.presets });
    },
  });
}

export function useSavedQuantStrategies() {
  return useQuery({
    queryKey: queryKeys.quant.strategies,
    queryFn: () => apiGet<QuantSavedStrategy[]>("/quant/strategies"),
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
    mutationFn: (strategyId: number) => apiDelete<DeleteResponse>(
      `/quant/strategies/${strategyId}`,
    ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.quant.strategies }),
  });
}

export function useQuantBacktests(pageSize = 50) {
  return useInfiniteQuery({
    queryKey: queryKeys.quant.runsHistory(pageSize),
    queryFn: ({ pageParam }) => apiGet<components["schemas"]["QuantBacktestList"]>("/quant/backtests", {
      limit: pageSize,
      offset: pageParam,
    }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, pages) => (
      lastPage.items.length < pageSize
        ? undefined
        : pages.reduce((count, page) => count + page.items.length, 0)
    ),
    refetchInterval: (query) => (
      query.state.data?.pages.some((page) => page.items.some((run) => isActive(run.status)))
        ? QUERY_CACHE_POLICIES.quantBacktestRuns.listActivePollMs
        : false
    ),
  });
}

export function useQuantBacktest(runId?: string) {
  return useQuery({
    queryKey: queryKeys.quant.run(runId ?? ""),
    queryFn: () => apiGet<QuantBacktestRun>(`/quant/backtests/${runId}`),
    enabled: Boolean(runId),
    refetchInterval: (query) => (
      isActive(query.state.data?.status)
        ? QUERY_CACHE_POLICIES.quantBacktestRuns.detailActivePollMs
        : false
    ),
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
  return useRunMutation((runId) => apiDelete<DeleteResponse>(
    `/quant/backtests/${runId}`,
  ));
}

export function useScanQuantParameterSensitivity() {
  return useMutation({
    mutationFn: ({ runId, request }: { runId: string; request: QuantParameterScanRequest }) =>
      apiPost<QuantParameterScanResult>(`/quant/backtests/${runId}/sensitivity-scan`, request),
  });
}

