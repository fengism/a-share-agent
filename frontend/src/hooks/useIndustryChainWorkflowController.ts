import { useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "../api/queryKeys";
import { streamIndustryChain, type IndustryChainProgress, type WorkflowCancelResult } from "../api/sse";
import { useIndustryChainWorkflowStore } from "../store/industryChainWorkflowStore";
import type { IndustryChainResearchScope, IndustryChainResult } from "../types/stock";
import {
  agentProcessFromEvents,
  applyAgentEvent,
  stopAgentProcess,
} from "../features/agent-process/agentProcess";
import { INDUSTRY_CHAIN_STAGES, industryStageIndex } from "../pages/IndustryChain/industryWorkflow";

interface IndustryChainWorkflowControllerOptions {
  onSuccess?: (result: IndustryChainResult) => void;
  onError?: (error: Error) => void;
  onCancelled?: (result: WorkflowCancelResult) => void;
}

export function useIndustryChainWorkflowController({
  onSuccess,
  onError,
  onCancelled,
}: IndustryChainWorkflowControllerOptions = {}) {
  const queryClient = useQueryClient();
  // 逐字段订阅：避免任何一次无关 patch（如 jobId 写入）触发整页重渲染；
  // 运行期每个 SSE 事件都会更新 agentProcess，未变化的字段不应引起重渲染
  const runId = useIndustryChainWorkflowStore((s) => s.runId);
  const jobId = useIndustryChainWorkflowStore((s) => s.jobId);
  const name = useIndustryChainWorkflowStore((s) => s.name);
  const status = useIndustryChainWorkflowStore((s) => s.status);
  const isAnalyzing = useIndustryChainWorkflowStore((s) => s.isAnalyzing);
  const isCancelling = useIndustryChainWorkflowStore((s) => s.isCancelling);
  const currentStage = useIndustryChainWorkflowStore((s) => s.currentStage);
  const stageMessage = useIndustryChainWorkflowStore((s) => s.stageMessage);
  const failedStage = useIndustryChainWorkflowStore((s) => s.failedStage);
  const result = useIndustryChainWorkflowStore((s) => s.result);
  const archiveId = useIndustryChainWorkflowStore((s) => s.archiveId);
  const error = useIndustryChainWorkflowStore((s) => s.error);
  const agentProcess = useIndustryChainWorkflowStore((s) => s.agentProcess);

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
      if (current.runId !== runId || !current.isAnalyzing) return;
      if (event.type === "error" && event.cancelled) {
        current.stopRun(runId, "cancelled");
        void queryClient.invalidateQueries({ queryKey: queryKeys.workflows.active });
      } else if (event.type === "stage_started" && event.stage) {
        const nextStage = industryStageIndex(event.stage);
        current.patch(runId, {
          currentStage: nextStage >= 0 ? nextStage : current.currentStage,
          stageMessage: event.message || "",
        });
      } else if (event.type === "stage_completed") {
        current.patch(runId, { stageMessage: event.message || "完成" });
      } else if (event.type === "stage_failed" && event.stage) {
        const failedStage = industryStageIndex(event.stage);
        current.patch(runId, {
          currentStage: failedStage >= 0 ? failedStage : current.currentStage,
          failedStage,
          stageMessage: event.message || "阶段执行失败",
        });
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
      if (current.runId !== runId || !current.isAnalyzing) return;
      current.patch(runId, {
        result,
        archiveId: result.archive_id || "",
        currentStage: result.archive_status === "failed"
          ? INDUSTRY_CHAIN_STAGES.length - 1
          : INDUSTRY_CHAIN_STAGES.length,
        failedStage: result.archive_status === "failed" ? INDUSTRY_CHAIN_STAGES.length - 1 : current.failedStage,
        stageMessage: result.archive_status === "failed"
          ? "分析完成，但存档失败"
          : result.quality_status === "degraded"
            ? "分析完成，但存在证据或质量提示"
            : "分析完成",
        isAnalyzing: false,
        isCancelling: false,
        status: result.archive_status === "failed" || result.quality_status === "degraded" ? "warning" : "success",
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
      onSuccess?.(result);
    }).catch((unknownError) => {
      const current = useIndustryChainWorkflowStore.getState();
      if (current.runId !== runId || !current.isAnalyzing) return;
      const error = unknownError instanceof Error ? unknownError : new Error("产业链分析失败");
      if (error.message === "已取消" || error.message === "已停止等待") {
        current.stopRun(runId, error.message === "已取消" ? "cancelled" : "detached");
      } else {
        current.patch(runId, {
          error: error.message, status: "error", isAnalyzing: false, isCancelling: false, stream: null,
          agentProcess: stopAgentProcess(current.agentProcess, "failed", error.message),
        });
        onError?.(error);
      }
      void queryClient.invalidateQueries({ queryKey: queryKeys.workflows.active });
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
      status: result.archive_status === "failed" || result.quality_status === "degraded" ? "warning" : "success",
      isAnalyzing: false,
      isCancelling: false,
      currentStage: -1,
      failedStage: -1,
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
      if (result) {
        void queryClient.invalidateQueries({ queryKey: queryKeys.workflows.active });
        onCancelled?.(result);
      }
      return result;
    } catch (unknownError) {
      const error = unknownError instanceof Error ? unknownError : new Error("停止产业研究失败");
      onError?.(error);
      return null;
    }
  }, [onCancelled, onError, queryClient]);

  return {
    runId,
    jobId,
    name,
    status,
    isAnalyzing,
    isCancelling,
    currentStage,
    stageMessage,
    failedStage,
    result,
    archiveId,
    error,
    agentProcess,
    runAnalysis,
    cancelAnalysis,
    loadResult,
    clearResult,
  };
}
