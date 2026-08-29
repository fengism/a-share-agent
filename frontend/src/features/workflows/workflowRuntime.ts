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
import { agentProcessFromEvents, applyAgentEvent } from "../agent-process/agentProcess";
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
  if (progress.type === "error") state.setRunError(identity, progress.error || "研究失败");
}

export function resumeAnalysisWorkflow(job: WorkflowJob) {
  const code = String(job.request.code || job.dedupe_key);
  const current = useAnalysisStore.getState();
  if (current.isAnalyzing && current.activeRun?.code === code) return;
  const identity = nextIdentity(code);
  current.beginRun(identity);
  const stream = resumeAnalysis(job.id, (progress) => applyAnalysisProgress(identity, progress));
  current.setRunStream(identity, stream);
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
    if (message !== "已停止等待" && message !== "已取消") state.setRunError(identity, message);
  }).finally(() => useAnalysisStore.getState().finishRun(identity));
}

function applyIndustryProgress(runId: number, progress: IndustryChainProgress) {
  const state = useIndustryChainWorkflowStore.getState();
  if (state.runId !== runId) return;
  if (progress.type === "stage_started" && progress.stage) {
    const index = industryStageIndex(progress.stage);
    state.patch(runId, {
      currentStage: index >= 0 ? index : state.currentStage,
      stageMessage: progress.message || "",
    });
  } else if (progress.type === "stage_completed") {
    state.patch(runId, { stageMessage: progress.message || "完成" });
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
  void stream.promise.then((result) => {
    const state = useIndustryChainWorkflowStore.getState();
    if (state.runId !== runId) return;
    state.patch(runId, {
      result,
      archiveId: result.archive_id || "",
      currentStage: INDUSTRY_CHAIN_STAGES.length,
      stageMessage: result.archive_status === "failed" ? "分析完成，但存档失败" : "分析完成",
      isAnalyzing: false,
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
    if (state.runId !== runId) return;
    const message = error instanceof Error ? error.message : "产业链分析失败";
    if (message !== "已停止等待" && message !== "已取消") {
      state.patch(runId, { error: message, isAnalyzing: false, stream: null });
    }
  });
}
