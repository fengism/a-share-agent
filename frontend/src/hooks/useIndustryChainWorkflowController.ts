import { useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "../api/queryKeys";
import { streamIndustryChain, type IndustryChainProgress, type WorkflowCancelResult } from "../api/sse";
import { useIndustryChainWorkflowStore } from "../store/industryChainWorkflowStore";
import type { IndustryChainResearchScope } from "../types/stock";
import {
  agentProcessFromEvents,
  applyAgentEvent,
} from "../features/agent-process/agentProcess";
import { INDUSTRY_CHAIN_STAGES, industryStageIndex } from "../pages/IndustryChain/industryWorkflow";

interface IndustryChainWorkflowControllerOptions {
  onSuccess?: () => void;
  onError?: (error: Error) => void;
  onCancelled?: (result: WorkflowCancelResult) => void;
}

export function useIndustryChainWorkflowController({
  onSuccess,
  onError,
  onCancelled,
}: IndustryChainWorkflowControllerOptions = {}) {
  const queryClient = useQueryClient();
  const state = useIndustryChainWorkflowStore();

  const runAnalysis = useCallback((
    name: string,
    scope: IndustryChainResearchScope,
    options: { force?: boolean } = {},
  ) => {
    const normalizedName = name.trim();
    if (!normalizedName || useIndustryChainWorkflowStore.getState().isAnalyzing) return false;
    const store = useIndustryChainWorkflowStore.getState();
    const runId = store.begin(normalizedName, scope);
    const stream = streamIndustryChain(normalizedName, (event: IndustryChainProgress) => {
      const current = useIndustryChainWorkflowStore.getState();
      if (current.runId !== runId) return;
      if (event.type === "stage_started" && event.stage) {
        const nextStage = industryStageIndex(event.stage);
        current.patch(runId, {
          currentStage: nextStage >= 0 ? nextStage : current.currentStage,
          stageMessage: event.message || "",
        });
      } else if (event.type === "stage_completed") {
        current.patch(runId, { stageMessage: event.message || "完成" });
      } else if (event.type === "agent_event" && event.agent_event) {
        current.patch(runId, {
          agentProcess: applyAgentEvent(current.agentProcess, event.agent_event),
        });
      }
    }, scope, options);
    store.setStream(runId, stream);
    void stream.started.then((submission) => {
      useIndustryChainWorkflowStore.getState().patch(runId, { jobId: submission.job.id });
      void queryClient.invalidateQueries({ queryKey: queryKeys.workflows.active });
    }).catch(() => undefined);

    void stream.promise.then((result) => {
      const current = useIndustryChainWorkflowStore.getState();
      if (current.runId !== runId) return;
      current.patch(runId, {
        result,
        archiveId: result.archive_id || "",
        currentStage: INDUSTRY_CHAIN_STAGES.length,
        stageMessage: result.archive_status === "failed" ? "分析完成，但存档失败" : "分析完成",
        isAnalyzing: false,
        agentProcess: current.agentProcess.plan || current.agentProcess.toolCalls.length > 0
          ? current.agentProcess
          : agentProcessFromEvents(result.agent_trace),
        stream: null,
      });
      void Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.workflows.industryChainHistoryRoot }),
        queryClient.invalidateQueries({ queryKey: queryKeys.workflows.industryChainLatest(normalizedName) }),
        queryClient.invalidateQueries({ queryKey: queryKeys.workflows.active }),
      ]);
      onSuccess?.();
    }).catch((unknownError) => {
      const current = useIndustryChainWorkflowStore.getState();
      if (current.runId !== runId) return;
      const error = unknownError instanceof Error ? unknownError : new Error("产业链分析失败");
      if (error.message === "已取消" || error.message === "已停止等待") return;
      current.patch(runId, { error: error.message, isAnalyzing: false, isCancelling: false, stream: null });
      onError?.(error);
    });
    return true;
  }, [onError, onSuccess, queryClient]);

  const loadResult = useCallback((name: string, result: ReturnType<typeof useIndustryChainWorkflowStore.getState>["result"], archiveId = "") => {
    if (!result) return;
    const store = useIndustryChainWorkflowStore.getState();
    const runId = store.runId + 1;
    useIndustryChainWorkflowStore.setState({
      ...store,
      runId,
      name,
      isAnalyzing: false,
      isCancelling: false,
      currentStage: -1,
      stageMessage: "",
      result,
      archiveId,
      error: "",
      agentProcess: agentProcessFromEvents(result.agent_trace),
      stream: null,
    });
  }, []);

  const clearResult = useCallback(() => {
    const store = useIndustryChainWorkflowStore.getState();
    store.patch(store.runId, { result: null, archiveId: "", error: "" });
  }, []);

  const cancelAnalysis = useCallback(async () => {
    try {
      const activeName = useIndustryChainWorkflowStore.getState().name;
      const result = await useIndustryChainWorkflowStore.getState().cancelActiveRun();
      if (result === "completed") {
        await Promise.all([
          queryClient.invalidateQueries({ queryKey: queryKeys.workflows.industryChainHistoryRoot }),
          queryClient.invalidateQueries({ queryKey: queryKeys.workflows.industryChainLatest(activeName) }),
        ]);
      }
      if (result) onCancelled?.(result);
      return result;
    } catch (unknownError) {
      const error = unknownError instanceof Error ? unknownError : new Error("停止产业研究失败");
      onError?.(error);
      return null;
    }
  }, [onCancelled, onError, queryClient]);

  return { ...state, runAnalysis, cancelAnalysis, loadResult, clearResult };
}
