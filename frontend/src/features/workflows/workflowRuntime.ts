import {
  resumeAnalysis,
  resumeIndustryChain,
  type AnalysisProgress,
  type IndustryChainProgress,
  type WorkflowStream,
} from "../../api/sse";
import { queryClient } from "../../api/queryClient";
import { queryKeys } from "../../api/queryKeys";
import { useAnalysisStore, type AnalysisRunIdentity } from "../../store/analysisStore";
import { useIndustryChainWorkflowStore } from "../../store/industryChainWorkflowStore";
import type { AnalysisResult, IndustryChainResult } from "../../types/stock";
import { normalizeAnalysisDate } from "../investment-research/analysisHistoryUrl";
import { agentProcessFromEvents, applyAgentEvent, stopAgentProcess } from "../agent-process/agentProcess";
import { INDUSTRY_CHAIN_STAGES, industryStageIndex } from "../../pages/IndustryChain/industryWorkflow";
import type { WorkflowJob } from "../../api/queries";

let resumeSequence = 0;

function nextIdentity(code: string): AnalysisRunIdentity {
  resumeSequence += 1;
  return { ownerId: "workflow-runtime", runId: `resume-${resumeSequence}`, code };
}

function applyAnalysisProgress(identity: AnalysisRunIdentity, progress: AnalysisProgress) {
  const state = useAnalysisStore.getState();
  if (state.activeRun?.runId !== identity.runId) return;
  if (progress.stage) {
    state.updateRunStage(
      identity,
      progress.stage,
      progress.total_stages,
      progress.type === "stage_started",
    );
  }
  if (progress.type === "agent_event" && progress.agent_event) {
    state.applyRunAgentEvent(identity, progress.agent_event);
  }
  if ((progress.type === "complete" || progress.type === "cached") && progress.result) {
    state.setRunResult(identity, progress.result);
  }
  if (progress.type === "error") {
    if (progress.cancelled) state.stopRun(identity, "cancelled");
    else state.setRunError(identity, progress.error || "研究失败");
  }
}

export function resumeAnalysisWorkflow(job: WorkflowJob) {
  const code = String(job.request.code || job.dedupe_key);
  const current = useAnalysisStore.getState();
  if (current.isAnalyzing && current.activeRun?.code === code) return;
  const identity = nextIdentity(code);
  current.beginRun(identity);
  const stream = resumeAnalysis(job.id, (progress) => applyAnalysisProgress(identity, progress));
  current.setRunStream(identity, stream);
  current.setRunJobId(identity, job.id);
  void stream.promise.then((result: AnalysisResult) => {
    const state = useAnalysisStore.getState();
    if (state.activeRun?.runId !== identity.runId) return;
    state.setRunResult(identity, result);
    const resultDate = normalizeAnalysisDate(result.analysis_date);
    if (resultDate) {
      queryClient.setQueryData(queryKeys.workflows.analysisHistorySnapshot(code, resultDate), result);
    }
    queryClient.setQueryData(queryKeys.stock.analysisPage(code), (cached: unknown) => (
      cached && typeof cached === "object" ? { ...cached, cached_analysis: result } : cached
    ));
    void queryClient.invalidateQueries({ queryKey: queryKeys.workflows.analysisHistoryRoot });
  }).catch((error: unknown) => {
    const state = useAnalysisStore.getState();
    if (state.activeRun?.runId !== identity.runId) return;
    const message = error instanceof Error ? error.message : "研究失败";
    if (message === "已停止等待" || message === "已取消") {
      state.stopRun(identity, message === "已取消" ? "cancelled" : "detached");
    } else {
      state.setRunError(identity, message);
    }
  }).finally(() => {
    useAnalysisStore.getState().finishRun(identity);
    void queryClient.invalidateQueries({ queryKey: queryKeys.workflows.active });
  });
}

function applyIndustryProgress(runId: number, progress: IndustryChainProgress) {
  const state = useIndustryChainWorkflowStore.getState();
  if (state.runId !== runId || !state.isAnalyzing) return;
  if (progress.type === "error" && progress.cancelled) {
    state.stopRun(runId, "cancelled");
    void queryClient.invalidateQueries({ queryKey: queryKeys.workflows.active });
  } else if (progress.type === "stage_started" && progress.stage) {
    const index = industryStageIndex(progress.stage);
    state.patch(runId, {
      currentStage: index >= 0 ? index : state.currentStage,
      stageMessage: progress.message || "",
    });
  } else if (progress.type === "stage_completed") {
    state.patch(runId, { stageMessage: progress.message || "完成" });
  } else if (progress.type === "stage_failed" && progress.stage) {
    const failedStage = industryStageIndex(progress.stage);
    state.patch(runId, {
      currentStage: failedStage >= 0 ? failedStage : state.currentStage,
      failedStage,
      stageMessage: progress.message || "阶段执行失败",
    });
  } else if (progress.type === "agent_event" && progress.agent_event) {
    state.patch(runId, { agentProcess: applyAgentEvent(state.agentProcess, progress.agent_event) });
  }
}

export function resumeIndustryChainWorkflow(job: WorkflowJob) {
  const name = String(job.request.name || job.dedupe_key);
  const current = useIndustryChainWorkflowStore.getState();
  if (current.isAnalyzing && current.name === name) return;
  const scope = (job.request.scope || {}) as Parameters<typeof current.begin>[1];
  const runId = current.begin(name, scope);
  const stream: WorkflowStream<IndustryChainResult> = resumeIndustryChain(
    job.id,
    (progress) => applyIndustryProgress(runId, progress),
  );
  current.setStream(runId, stream);
  current.patch(runId, { jobId: job.id });
  void stream.promise.then((result) => {
    const state = useIndustryChainWorkflowStore.getState();
    if (state.runId !== runId || !state.isAnalyzing) return;
    state.patch(runId, {
      result,
      archiveId: result.archive_id || "",
      currentStage: result.archive_status === "failed"
        ? INDUSTRY_CHAIN_STAGES.length - 1
        : INDUSTRY_CHAIN_STAGES.length,
      failedStage: result.archive_status === "failed" ? INDUSTRY_CHAIN_STAGES.length - 1 : state.failedStage,
      stageMessage: result.archive_status === "failed"
        ? "分析完成，但存档失败"
        : result.quality_status === "degraded"
          ? "分析完成，但存在证据或质量提示"
          : "分析完成",
      isAnalyzing: false,
      isCancelling: false,
      status: result.archive_status === "failed" || result.quality_status === "degraded" ? "warning" : "success",
      agentProcess: state.agentProcess.plan || state.agentProcess.toolCalls.length > 0
        ? state.agentProcess
        : agentProcessFromEvents(result.agent_trace),
      stream: null,
    });
    void Promise.all([
      queryClient.invalidateQueries({ queryKey: queryKeys.workflows.industryChainHistoryRoot }),
      queryClient.invalidateQueries({ queryKey: queryKeys.workflows.industryChainLatest(name) }),
      queryClient.invalidateQueries({ queryKey: queryKeys.workflows.active }),
    ]);
  }).catch((error: unknown) => {
    const state = useIndustryChainWorkflowStore.getState();
    if (state.runId !== runId || !state.isAnalyzing) return;
    const message = error instanceof Error ? error.message : "产业链分析失败";
    if (message === "已停止等待" || message === "已取消") {
      state.stopRun(runId, message === "已取消" ? "cancelled" : "detached");
    } else {
      state.patch(runId, {
        error: message, status: "error", isAnalyzing: false, isCancelling: false, stream: null,
        agentProcess: stopAgentProcess(state.agentProcess, "failed", message),
      });
    }
    void queryClient.invalidateQueries({ queryKey: queryKeys.workflows.active });
  });
}
