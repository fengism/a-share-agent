import { beforeEach, describe, expect, it, vi } from "vitest";
import type { WorkflowJob } from "../../api/queries";
import type { AnalysisProgress, IndustryChainProgress } from "../../api/sse";
import type { AnalysisResult, IndustryChainResult } from "../../types/stock";
import { useIndustryChainWorkflowStore as store } from "../../store/industryChainWorkflowStore";
import { useAnalysisStore } from "../../store/analysisStore";
import { resumeAnalysisWorkflow, resumeIndustryChainWorkflow } from "./workflowRuntime";

const { resumeAnalysis, resumeIndustryChain, invalidateQueries, setQueryData } = vi.hoisted(() => ({
  resumeAnalysis: vi.fn(), setQueryData: vi.fn(), resumeIndustryChain: vi.fn(), invalidateQueries: vi.fn().mockResolvedValue(undefined),
}));
vi.mock("../../api/sse", () => ({ resumeIndustryChain, resumeAnalysis }));
vi.mock("../../api/queryClient", () => ({ queryClient: { invalidateQueries, setQueryData } }));

const report = { name: "机器人", summary: "报告" } as IndustryChainResult;
const job: WorkflowJob = {
  id: "resume-job",
  kind: "industry_chain",
  request: { name: "机器人", scope: {} },
  dedupe_key: "机器人",
  status: "running",
  attempts: 1,
  max_attempts: 1,
  created_at: 1,
  updated_at: 1,
  completed_at: null,
  last_error: null,
};
function setup() {
  let resolve!: (value: IndustryChainResult) => void;
  let reject!: (error: Error) => void;
  let progress!: (value: IndustryChainProgress) => void;
  const promise = new Promise<IndustryChainResult>((res, rej) => { resolve = res; reject = rej; });
  const stream = { promise, started: Promise.resolve({ job, attached: true }), cancel: vi.fn().mockResolvedValue("detached"), detach: vi.fn() };
  resumeIndustryChain.mockImplementation((_jobId, onProgress) => { progress = onProgress; return stream; });
  resumeIndustryChainWorkflow(job);
  return { resolve, reject, progress, promise, stream };
}

beforeEach(() => {
  store.getState().clear();
  useAnalysisStore.getState().resetAnalysis();
  resumeAnalysis.mockReset();
  resumeIndustryChain.mockReset();
  invalidateQueries.mockClear();
  setQueryData.mockClear();
});

describe("resumed industry workflows", () => {
  it("records job identity and ignores late progress/results after stopping waiting", async () => {
    const test = setup();
    expect(store.getState()).toMatchObject({ jobId: job.id, status: "running" });
    test.progress({ type: "stage_started", stage: "research" });
    await store.getState().cancelActiveRun();
    test.progress({ type: "stage_started", stage: "synthesis" });
    test.resolve(report);
    await test.promise;
    expect(store.getState()).toMatchObject({ status: "detached", isAnalyzing: false, currentStage: 0, result: null });
  });

  it("handles server cancellation while attached", async () => {
    const test = setup();
    test.progress({ type: "error", cancelled: true, message: "产业链分析已取消" });
    test.reject(new Error("产业链分析已取消"));
    await test.promise.catch(() => undefined);
    expect(store.getState()).toMatchObject({ status: "cancelled", isAnalyzing: false, error: "" });
    expect(invalidateQueries).toHaveBeenCalled();
  });

  it.each(["已停止等待", "已取消", "模型失败"])("settles rejected stream: %s", async (message) => {
    const test = setup();
    test.reject(new Error(message));
    await test.promise.catch(() => undefined);
    expect(store.getState()).toMatchObject({
      status: message === "已停止等待" ? "detached" : message === "已取消" ? "cancelled" : "error",
      isAnalyzing: false, isCancelling: false, stream: null,
    });
  });

  it("records successful completion explicitly", async () => {
    const test = setup();
    test.resolve(report);
    await test.promise;
    expect(store.getState()).toMatchObject({ status: "success", isAnalyzing: false, isCancelling: false, result: report, currentStage: 5 });
  });


  it("restores an archive-failed industry report as warning", async () => {
    const test = setup();
    test.progress({ type: "stage_failed", stage: "archive", message: "报告已生成，但存档失败" });
    test.resolve({ ...report, archive_status: "failed", quality_status: "complete" });
    await test.promise;
    expect(store.getState()).toMatchObject({
      status: "warning", isAnalyzing: false, currentStage: 4, failedStage: 4,
    });
  });

});

const analysisJob: WorkflowJob = { ...job, id: "stock-job", kind: "analysis", request: { code: "600519" }, dedupe_key: "600519" };
const analysisReport = { stock_code: "600519", analysis_date: "20260924" } as AnalysisResult;
function setupAnalysis() {
  let resolve!: (value: AnalysisResult) => void;
  let reject!: (error: Error) => void;
  let progress!: (value: AnalysisProgress) => void;
  const promise = new Promise<AnalysisResult>((res, rej) => { resolve = res; reject = rej; });
  const stream = { promise, started: Promise.resolve({ job: analysisJob, attached: true }),
    cancel: vi.fn().mockResolvedValue("detached"), detach: vi.fn() };
  resumeAnalysis.mockImplementation((_jobId, callback) => { progress = callback; return stream; });
  resumeAnalysisWorkflow(analysisJob);
  progress({ type: "stage_started", total_stages: 3,
    stage: { stage: 1, name: "证据校验", status: "started" } });
  progress({ type: "agent_event", total_stages: 3, agent_event: {
    type: "tool_call", tool_call: { id: "fetch", type: "function",
      function: { name: "web_fetch", arguments: "{}" } },
  } });
  // Drain the runtime's then/catch/finally chain, including rejected streams.
  const settled = () => promise.catch(() => undefined).then(() => undefined).then(() => undefined);
  return { resolve, reject, progress, stream, settled };
}

describe("resumed analysis workflows", () => {
  it.each(["cancelled", "detached"] as const)("records identity and ignores late events after %s", async (outcome) => {
    const test = setupAnalysis();
    expect(useAnalysisStore.getState()).toMatchObject({ jobId: analysisJob.id, isAnalyzing: true });
    test.stream.cancel.mockResolvedValue(outcome);
    await useAnalysisStore.getState().cancelActiveRun();
    test.progress({ type: "stage_started", total_stages: 3,
      stage: { stage: 3, name: "迟到阶段", status: "started" } });
    test.progress({ type: "complete", total_stages: 3, result: analysisReport });
    test.resolve(analysisReport);
    await test.settled();
    expect(useAnalysisStore.getState()).toMatchObject({
      isAnalyzing: false, isCancelling: false, activeRun: null, activeStream: null,
      analysisResult: null, analysisError: null, currentStageIndex: 0,
      agentProcess: { termination: outcome, toolCalls: [{ isExecuting: false, isCancelled: true }] },
    });
    expect(setQueryData).not.toHaveBeenCalled();
  });

  it("handles cancellation reported by the server", async () => {
    const test = setupAnalysis();
    test.progress({ type: "error", total_stages: 3, cancelled: true, error: "个股研究已取消" });
    test.reject(new Error("个股研究已取消"));
    await test.settled();
    expect(useAnalysisStore.getState()).toMatchObject({
      isAnalyzing: false, analysisError: null,
      agentProcess: { termination: "cancelled", toolCalls: [{ isExecuting: false }] },
    });
    expect(invalidateQueries).toHaveBeenCalled();
  });

  it.each(["已取消", "已停止等待", "模型失败"])("settles rejected streams: %s", async (message) => {
    const test = setupAnalysis();
    test.reject(new Error(message));
    await test.settled();
    expect(useAnalysisStore.getState()).toMatchObject({
      isAnalyzing: false, isCancelling: false, activeRun: null, activeStream: null,
      analysisError: message === "模型失败" ? message : null,
      agentProcess: {
        termination: message === "已取消" ? "cancelled" : message === "已停止等待" ? "detached" : "failed",
        toolCalls: [{ isExecuting: false }],
      },
    });
  });

  it("still accepts a result after cancellation reports the job already completed", async () => {
    const test = setupAnalysis();
    test.stream.cancel.mockResolvedValue("completed");
    await useAnalysisStore.getState().cancelActiveRun();
    expect(useAnalysisStore.getState().isAnalyzing).toBe(true);
    test.resolve(analysisReport);
    await test.settled();
    expect(useAnalysisStore.getState()).toMatchObject({
      analysisResult: analysisReport, isAnalyzing: false, isCancelling: false, activeRun: null,
    });
    expect(useAnalysisStore.getState().agentProcess.termination).toBeUndefined();
    expect(setQueryData).toHaveBeenCalled();
  });
});
