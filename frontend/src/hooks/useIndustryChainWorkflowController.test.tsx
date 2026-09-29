import type { PropsWithChildren } from "react";
import { act, renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { IndustryChainProgress, WorkflowCancelResult } from "../api/sse";
import { queryKeys } from "../api/queryKeys";
import { useIndustryChainWorkflowStore as store } from "../store/industryChainWorkflowStore";
import type { IndustryChainResearchScope, IndustryChainResult } from "../types/stock";
import { useIndustryChainWorkflowController } from "./useIndustryChainWorkflowController";

const { streamIndustryChain } = vi.hoisted(() => ({ streamIndustryChain: vi.fn() }));
vi.mock("../api/sse", () => ({ streamIndustryChain }));

const scope: IndustryChainResearchScope = { region: "china", time_range: "one_year", company_scope: "a_share" };
const report: IndustryChainResult = {
  name: "机器人", summary: "摘要", upstream: [], midstream: [], downstream: [],
  drivers: [], risks: [], key_stocks: [], llm_review: "报告", charts: [],
};
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}
async function setup() {
  const completion = deferred<IndustryChainResult>();
  const cancellation = deferred<WorkflowCancelResult>();
  const stream = {
    promise: completion.promise,
    started: Promise.resolve({ job: { id: "job-1" }, attached: false }),
    cancel: vi.fn(() => cancellation.promise),
    detach: vi.fn(),
  };
  let progress!: (event: IndustryChainProgress) => void;
  streamIndustryChain.mockImplementation((_name, onProgress) => { progress = onProgress; return stream; });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(queryClient, "invalidateQueries");
  const onSuccess = vi.fn();
  const onError = vi.fn();
  const onCancelled = vi.fn();
  const hook = renderHook(() => useIndustryChainWorkflowController({ onSuccess, onError, onCancelled }), {
    wrapper: ({ children }: PropsWithChildren) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>,
  });
  await act(async () => { hook.result.current.runAnalysis("机器人", scope); await stream.started; });
  return { ...hook, completion, cancellation, stream, progress, onSuccess, onError, onCancelled, invalidate };
}

beforeEach(() => { store.getState().clear(); streamIndustryChain.mockReset(); });

describe("industry workflow cancellation", () => {
  it.each(["cancelled", "detached"] as const)("settles %s only after acknowledgement and ignores late events", async (outcome) => {
    const test = await setup();
    act(() => test.progress({ type: "stage_started", stage: "research" }));
    let pending!: ReturnType<typeof test.result.current.cancelAnalysis>;
    act(() => { pending = test.result.current.cancelAnalysis(); });
    expect(test.result.current).toMatchObject({ status: "running", isAnalyzing: true, isCancelling: true });
    await act(async () => { expect(await store.getState().cancelActiveRun()).toBeNull(); });
    await act(async () => { test.cancellation.resolve(outcome); await pending; });
    expect(test.result.current).toMatchObject({ status: outcome, isAnalyzing: false, isCancelling: false, result: null });
    expect(test.result.current.agentProcess.termination).toBe(outcome);
    expect(test.result.current.stageMessage).toContain(outcome === "cancelled" ? "已取消" : "后台共享任务仍在运行");
    expect(test.onCancelled).toHaveBeenCalledWith(outcome);
    expect(test.invalidate).toHaveBeenCalledWith({ queryKey: queryKeys.workflows.active });
    await act(async () => {
      test.progress({ type: "stage_started", stage: "draft", message: "错误的晚到状态" });
      test.progress({ type: "agent_event", agent_event: { type: "status", content: "仍在运行" } });
      test.completion.resolve(report);
      await test.completion.promise;
    });
    expect(test.result.current).toMatchObject({ status: outcome, currentStage: 0, result: null });
    expect(test.onSuccess).not.toHaveBeenCalled();
    expect(test.onError).not.toHaveBeenCalled();
  });

  it("keeps receiving the real result when cancellation observes an already completed job", async () => {
    const test = await setup();
    await act(async () => {
      const pending = test.result.current.cancelAnalysis();
      test.cancellation.resolve("completed");
      await pending;
    });
    expect(test.result.current).toMatchObject({ status: "running", isAnalyzing: true, result: null });
    expect(store.getState().stream).toBe(test.stream);
    await act(async () => { test.completion.resolve(report); await test.completion.promise; });
    expect(test.result.current).toMatchObject({ status: "success", result: report, currentStage: 5, isAnalyzing: false, isCancelling: false });
    expect(test.onSuccess).toHaveBeenCalledOnce();
  });

  it("does not let a late cancellation response overwrite an already received result", async () => {
    const test = await setup();
    let pending!: ReturnType<typeof test.result.current.cancelAnalysis>;
    act(() => { pending = test.result.current.cancelAnalysis(); });
    await act(async () => { test.completion.resolve(report); await test.completion.promise; });
    await act(async () => { test.cancellation.resolve("completed"); await pending; });
    expect(test.result.current).toMatchObject({ status: "success", result: report, stageMessage: "分析完成", isCancelling: false });
  });

  it("keeps running after a failed cancellation and allows retry", async () => {
    const test = await setup();
    await act(async () => {
      const pending = test.result.current.cancelAnalysis();
      test.cancellation.reject(new Error("暂时不可用"));
      await pending;
    });
    expect(test.result.current).toMatchObject({ status: "running", isAnalyzing: true, isCancelling: false, error: "" });
    expect(test.result.current.stageMessage).toContain("任务继续运行");
    expect(test.onError).toHaveBeenCalledOnce();
    expect(store.getState().stream).toBe(test.stream);
    test.stream.cancel.mockResolvedValueOnce("cancelled");
    await act(async () => { await test.result.current.cancelAnalysis(); });
    expect(test.result.current.status).toBe("cancelled");
  });

  it("settles cancellation received from another tab without reporting failure", async () => {
    const test = await setup();
    await act(async () => {
      test.progress({ type: "error", cancelled: true, message: "产业链分析已取消" });
      test.completion.reject(new Error("产业链分析已取消"));
      await test.completion.promise.catch(() => undefined);
    });
    expect(test.result.current).toMatchObject({ status: "cancelled", isAnalyzing: false, error: "" });
    expect(test.onError).not.toHaveBeenCalled();
  });

  it.each(["已取消", "已停止等待"])("settles stream rejection: %s", async (message) => {
    const test = await setup();
    await act(async () => { test.completion.reject(new Error(message)); await test.completion.promise.catch(() => undefined); });
    expect(test.result.current.status).toBe(message === "已取消" ? "cancelled" : "detached");
    expect(test.result.current.isAnalyzing).toBe(false);
    expect(test.onError).not.toHaveBeenCalled();
  });

  it("stops progress on a genuine analysis failure", async () => {
    const test = await setup();
    await act(async () => { test.completion.reject(new Error("模型不可用")); await test.completion.promise.catch(() => undefined); });
    expect(test.result.current).toMatchObject({ status: "error", isAnalyzing: false, error: "模型不可用" });
    expect(test.result.current.agentProcess.termination).toBe("failed");
    expect(test.onError).toHaveBeenCalledOnce();
  });

  it("clears cancellation when loading a report or starting a new run", async () => {
    const test = await setup();
    await act(async () => { test.cancellation.resolve("cancelled"); await test.result.current.cancelAnalysis(); });
    act(() => test.result.current.loadResult("机器人", report, "archive-1"));
    expect(test.result.current).toMatchObject({ status: "success", result: report, archiveId: "archive-1" });
    expect(test.result.current.agentProcess.termination).toBeUndefined();
    await act(async () => { test.result.current.runAnalysis("芯片", scope); });
    expect(test.result.current).toMatchObject({ status: "running", isAnalyzing: true, result: null });
    expect(test.result.current.agentProcess.termination).toBeUndefined();
  });

  it("ignores an old run after clearing the user scope and starting again", async () => {
    const old = await setup();
    const oldRunId = store.getState().runId;
    act(() => store.getState().clear());
    const next = await setup();
    expect(store.getState().runId).toBeGreaterThan(oldRunId);
    await act(async () => {
      old.progress({ type: "stage_started", stage: "draft" });
      old.completion.resolve(report);
      await old.completion.promise;
    });
    expect(next.result.current).toMatchObject({ status: "running", currentStage: -1, result: null });
    expect(old.onSuccess).not.toHaveBeenCalled();
  });

  it("surfaces a degraded completion instead of plain success copy", async () => {
    const test = await setup();
    await act(async () => {
      test.completion.resolve({ ...report, quality_status: "degraded" });
      await test.completion.promise;
    });
    expect(test.result.current.status).toBe("warning");
    expect(test.result.current.stageMessage).toContain("质量提示");
  });


  it("keeps a generated report but marks archive failure as a warning stage", async () => {
    const test = await setup();
    act(() => test.progress({ type: "stage_failed", stage: "archive", message: "报告已生成，但存档失败" }));
    expect(test.result.current).toMatchObject({ currentStage: 4, failedStage: 4 });
    await act(async () => {
      test.completion.resolve({ ...report, archive_status: "failed", quality_status: "complete" });
      await test.completion.promise;
    });
    expect(test.result.current).toMatchObject({
      status: "warning", currentStage: 4, failedStage: 4,
      result: expect.objectContaining({ archive_status: "failed" }),
    });
    expect(test.result.current.stageMessage).toContain("存档失败");
    expect(test.onError).not.toHaveBeenCalled();
  });

});
