import { useCallback, useEffect, useMemo, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { InfiniteData } from "@tanstack/react-query";
import { queryKeys } from "../api/queryKeys";
import {
  agentProcessFromEvents,
  createAgentProcessState,
  hasAgentProcess,
} from "../features/agent-process/agentProcess";
import {
  streamAnalysis,
  type AnalysisProgress,
  type AnalysisStage,
  type WorkflowCancelResult,
  type WorkflowStream,
} from "../api/sse";
import {
  useAnalysisStore,
  type AnalysisRunIdentity,
} from "../store/analysisStore";
import type { AnalysisHistoryItem, AnalysisPageData, AnalysisResult } from "../types/stock";
import { normalizeAnalysisDate } from "../features/investment-research/analysisHistoryUrl";

interface AnalysisWorkflowControllerOptions {
  code?: string;
  historyDate?: string;
  cachedResult?: AnalysisResult | null;
  historicalResult?: AnalysisResult | null;
  onSuccess?: (result: AnalysisResult) => void;
  onError?: (error: Error) => void;
  onCancelled?: (result: WorkflowCancelResult) => void;
  preferredRoute?: "analysis" | "investment-research";
}

interface RunRequest {
  force?: boolean;
}

let ownerSequence = 0;
let runSequence = 0;

function nextOwnerId() {
  ownerSequence += 1;
  return `analysis-owner-${ownerSequence}`;
}

function nextRunIdentity(ownerId: string, code: string): AnalysisRunIdentity {
  runSequence += 1;
  return { ownerId, runId: `analysis-run-${runSequence}`, code };
}

function historySummary(result: AnalysisResult): AnalysisHistoryItem {
  return {
    stock_code: result.stock_code,
    stock_name: result.stock_name,
    analysis_date: result.analysis_date,
    current_price: result.current_price,
    overall_rating: result.overall_rating,
    signal: result.signal,
    confidence: result.confidence,
    can_delete: true,
  };
}

function upsertHistoryItem(
  current: InfiniteData<AnalysisHistoryItem[]> | undefined,
  result: AnalysisResult,
) {
  if (!current) return current;
  const resultDate = normalizeAnalysisDate(result.analysis_date);
  const replacement = historySummary(result);
  const pages = current.pages.map((page) => page.filter((item) => !(
    item.stock_code === result.stock_code
    && normalizeAnalysisDate(item.analysis_date) === resultDate
  )));
  const firstPage = pages[0] ?? [];
  pages[0] = [replacement, ...firstPage];
  return { ...current, pages };
}

export function useAnalysisWorkflowController({
  code = "",
  historyDate = "",
  cachedResult,
  historicalResult,
  onSuccess,
  onError,
  onCancelled,
  preferredRoute = "analysis",
}: AnalysisWorkflowControllerOptions) {
  const queryClient = useQueryClient();
  const currentCode = useAnalysisStore((state) => state.currentCode);
  const analysisResult = useAnalysisStore((state) => state.analysisResult);
  const isAnalyzing = useAnalysisStore((state) => state.isAnalyzing);
  const isCancelling = useAnalysisStore((state) => state.isCancelling);
  const stages = useAnalysisStore((state) => state.analysisStages);
  const currentStageIndex = useAnalysisStore((state) => state.currentStageIndex);
  const agentProcess = useAnalysisStore((state) => state.agentProcess);
  const analysisError = useAnalysisStore((state) => state.analysisError);
  const activeRun = useAnalysisStore((state) => state.activeRun);
  const ownerIdRef = useRef(nextOwnerId());
  const identityRef = useRef<AnalysisRunIdentity | null>(null);
  const streamRef = useRef<WorkflowStream<AnalysisResult> | null>(null);
  const contextKeyRef = useRef("");
  const callbacksRef = useRef({ onSuccess, onError, onCancelled });

  useEffect(() => {
    callbacksRef.current = { onSuccess, onError, onCancelled };
  }, [onCancelled, onError, onSuccess]);

  useEffect(() => {
    const contextKey = `${code}:${historyDate}`;
    if (contextKeyRef.current === contextKey) return;
    contextKeyRef.current = contextKey;
    const state = useAnalysisStore.getState();
    const active = state.activeRun;
    if (active?.code === code && state.activeStream) {
      identityRef.current = active;
      streamRef.current = state.activeStream;
      state.claimContext(code, preferredRoute);
      return;
    }
    identityRef.current = null;
    streamRef.current = null;
    state.claimContext(code, preferredRoute);
  }, [code, historyDate, preferredRoute]);

  useEffect(() => () => {
    streamRef.current = null;
    contextKeyRef.current = "";
  }, []);

  const ownsIdentity = useCallback((identity: AnalysisRunIdentity) => {
    const active = useAnalysisStore.getState().activeRun;
    return active?.ownerId === identity.ownerId
      && active.runId === identity.runId
      && active.code === identity.code;
  }, []);

  const synchronizeResult = useCallback((result: AnalysisResult) => {
    const resultCode = result.stock_code || code;
    const resultDate = normalizeAnalysisDate(result.analysis_date);
    queryClient.setQueryData<AnalysisPageData>(queryKeys.stock.analysisPage(resultCode), (current) => (
      current ? { ...current, cached_analysis: result } : current
    ));
    if (resultDate) {
      queryClient.setQueryData(
        queryKeys.workflows.analysisHistorySnapshot(resultCode, resultDate),
        result,
      );
    }
    queryClient.setQueriesData<InfiniteData<AnalysisHistoryItem[]>>(
      { queryKey: queryKeys.workflows.analysisHistoryRoot },
      (current) => upsertHistoryItem(current, result),
    );
    void queryClient.invalidateQueries({ queryKey: queryKeys.workflows.analysisHistoryRoot });
  }, [code, queryClient]);

  const handleProgress = useCallback((
    progress: AnalysisProgress,
    identity: AnalysisRunIdentity,
  ) => {
    if (!ownsIdentity(identity)) return;
    const state = useAnalysisStore.getState();
    switch (progress.type) {
      case "stage_started":
        if (progress.stage) {
          state.updateRunStage(identity, progress.stage as AnalysisStage, progress.total_stages, true);
        }
        break;
      case "stage_completed":
      case "stage_failed":
        if (progress.stage) state.updateRunStage(identity, progress.stage as AnalysisStage, progress.total_stages);
        break;
      case "agent_event":
        if (progress.agent_event) state.applyRunAgentEvent(identity, progress.agent_event);
        break;
      case "complete":
      case "cached":
        if (progress.result) state.setRunResult(identity, progress.result);
        break;
      case "error":
        state.setRunError(identity, progress.error || "研究失败");
        break;
    }
  }, [ownsIdentity]);

  const runAnalysis = useCallback(async ({ force = false }: RunRequest = {}) => {
    if (!code || streamRef.current || useAnalysisStore.getState().isCancelling) return null;
    const identity = nextRunIdentity(ownerIdRef.current, code);
    identityRef.current = identity;
    const state = useAnalysisStore.getState();
    state.beginRun(identity);

    const stream = streamAnalysis(
      code,
      (progress) => handleProgress(progress, identity),
      { force },
    );
    streamRef.current = stream;
    state.setRunStream(identity, stream);
    void stream.started.then((submission) => {
      useAnalysisStore.getState().setRunJobId(identity, submission.job.id);
      void queryClient.invalidateQueries({ queryKey: queryKeys.workflows.active });
    }).catch(() => undefined);

    try {
      const result = await stream.promise;
      synchronizeResult(result);
      if (!ownsIdentity(identity)) return result;
      useAnalysisStore.getState().setRunResult(identity, result);
      callbacksRef.current.onSuccess?.(result);
      void queryClient.invalidateQueries({ queryKey: queryKeys.workflows.active });
      return result;
    } catch (unknownError) {
      if (!ownsIdentity(identity)) return null;
      const error = unknownError instanceof Error ? unknownError : new Error("未知错误");
      if (error.message === "已取消" || error.message === "已停止等待") return null;
      useAnalysisStore.getState().setRunError(identity, error.message);
      callbacksRef.current.onError?.(error);
      void queryClient.invalidateQueries({ queryKey: queryKeys.workflows.active });
      return null;
    } finally {
      if (ownsIdentity(identity)) {
        streamRef.current = null;
        identityRef.current = null;
        useAnalysisStore.getState().finishRun(identity);
      }
    }
  }, [code, handleProgress, ownsIdentity, queryClient, synchronizeResult]);

  const cancelAnalysis = useCallback(async () => {
    const active = useAnalysisStore.getState().activeRun;
    if (!active || active.code !== code) return null;
    const callback = callbacksRef.current.onCancelled;
    try {
      const result = await useAnalysisStore.getState().cancelActiveRun();
      if (result === "completed") {
        await queryClient.invalidateQueries({ queryKey: queryKeys.stock.analysisPage(code) });
      }
      if (result) callback?.(result);
      void queryClient.invalidateQueries({ queryKey: queryKeys.workflows.active });
      return result;
    } catch (unknownError) {
      const error = unknownError instanceof Error ? unknownError : new Error("取消失败");
      callbacksRef.current.onError?.(error);
      return null;
    }
  }, [code, queryClient]);

  const displayResult = useMemo(() => {
    if (historyDate) return historicalResult ?? null;
    if (currentCode === code && analysisResult) return analysisResult;
    return cachedResult ?? null;
  }, [analysisResult, cachedResult, code, currentCode, historicalResult, historyDate]);

  const ownsCurrentContext = currentCode === code;
  const ownsCurrentRun = activeRun?.code === code;
  const displayAgentProcess = useMemo(() => {
    if (historyDate) return agentProcessFromEvents(displayResult?.agent_trace);
    if (ownsCurrentRun || (ownsCurrentContext && hasAgentProcess(agentProcess))) {
      return agentProcess;
    }
    return agentProcessFromEvents(displayResult?.agent_trace);
  }, [
    agentProcess,
    displayResult?.agent_trace,
    historyDate,
    ownsCurrentContext,
    ownsCurrentRun,
  ]);
  return {
    displayResult,
    result: ownsCurrentContext ? analysisResult : null,
    isAnalyzing: ownsCurrentRun && isAnalyzing,
    isCancelling: ownsCurrentRun && isCancelling,
    analysisError: ownsCurrentContext ? analysisError : null,
    stages: ownsCurrentContext ? stages : [],
    currentStageIndex: ownsCurrentContext ? currentStageIndex : 0,
    agentProcess: ownsCurrentContext || displayResult
      ? displayAgentProcess
      : createAgentProcessState(),
    runAnalysis,
    cancelAnalysis,
  };
}
