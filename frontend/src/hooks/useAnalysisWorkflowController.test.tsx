import type { PropsWithChildren } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AnalysisProgress, WorkflowCancelResult } from "../api/sse";
import { queryKeys } from "../api/queryKeys";
import { useAnalysisStore } from "../store/analysisStore";
import type { AnalysisPageData, AnalysisResult } from "../types/stock";
import { useAnalysisWorkflowController } from "./useAnalysisWorkflowController";

const { streamAnalysis } = vi.hoisted(() => ({ streamAnalysis: vi.fn() }));
vi.mock("../api/sse", async (importOriginal) => ({
  ...await importOriginal<typeof import("../api/sse")>(),
  streamAnalysis,
}));

const result = {
  stock_code: "600519",
  stock_name: "贵州茅台",
  analysis_date: "2026-08-26",
  current_price: 1500,
  overall_rating: 8,
  signal: "buy",
  confidence: 0.8,
} as AnalysisResult;
const cachedResult = { ...result, analysis_date: "20260825" };
const historicalResult = { ...result, analysis_date: "20260824" };

function createWrapper(queryClient: QueryClient) {
  return function Wrapper({ children }: PropsWithChildren) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

function pendingStream() {
  return {
    promise: new Promise<AnalysisResult>(() => undefined),
    started: Promise.resolve({ job: { id: "job" }, attached: false }),
    cancel: vi.fn().mockResolvedValue("cancelled"),
    detach: vi.fn(),
  };
}

function controlledStream() {
  let resolve!: (value: AnalysisResult) => void;
  let reject!: (error: Error) => void;
  let progress!: (value: AnalysisProgress) => void;
  let acknowledge!: (outcome: WorkflowCancelResult) => void;
  let rejectCancel!: (error: Error) => void;
  const stream = {
    promise: new Promise<AnalysisResult>((res, rej) => { resolve = res; reject = rej; }),
    started: Promise.resolve({ job: { id: "controlled-job" }, attached: false }),
    cancel: vi.fn(() => new Promise<WorkflowCancelResult>((res, rej) => { acknowledge = res; rejectCancel = rej; })),
    detach: vi.fn(),
  };
  streamAnalysis.mockImplementationOnce((_code, callback) => { progress = callback; return stream; });
  return { stream, resolve, reject, progress: (value: AnalysisProgress) => progress(value),
    acknowledge: (value: WorkflowCancelResult) => acknowledge(value),
    rejectCancel: (error: Error) => rejectCancel(error) };
}

function sendRunningProgress(progress: (value: AnalysisProgress) => void) {
  progress({ type: "stage_started", total_stages: 3,
    stage: { stage: 1, name: "数据采集与证据校验", status: "started" } });
  progress({ type: "agent_event", total_stages: 3, agent_event: {
    type: "tool_call", tool_call: { id: "fetch", type: "function",
      function: { name: "web_fetch", arguments: "{}" } },
  } });
}

describe("useAnalysisWorkflowController", () => {
  beforeEach(() => {
    streamAnalysis.mockReset();
    useAnalysisStore.getState().resetAnalysis();
  });

  it("maps progress, forwards force, synchronizes caches, and returns a result", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    queryClient.setQueryData<AnalysisPageData>(queryKeys.stock.analysisPage("600519"), {
      stock_info: null,
      kline: null,
      intraday: null,
      valuation: null,
      cached_analysis: null,
      key_levels: null,
      chip_distribution: null,
    });
    streamAnalysis.mockImplementation((_code, onProgress) => {
      onProgress({
        type: "stage_started",
        total_stages: 3,
        stage: { stage: 1, name: "证据调研", status: "started" },
      });
      onProgress({
        type: "agent_event",
        total_stages: 3,
        agent_event: {
          type: "plan",
          plan: {
            summary: "先检查财务和估值",
            steps: [],
          },
        },
      });
      return { promise: Promise.resolve(result), started: Promise.resolve({ job: { id: "job" }, attached: false }), cancel: vi.fn(), detach: vi.fn() };
    });
    const onSuccess = vi.fn();
    const { result: hook } = renderHook(
      () => useAnalysisWorkflowController({ code: "600519", onSuccess }),
      { wrapper: createWrapper(queryClient) },
    );

    await act(async () => {
      await hook.current.runAnalysis({ force: true });
    });

    expect(streamAnalysis).toHaveBeenCalledWith("600519", expect.any(Function), { force: true });
    expect(onSuccess).toHaveBeenCalledWith(result);
    expect(hook.current.displayResult).toBe(result);
    expect(hook.current.stages[0]?.name).toBe("证据调研");
    expect(hook.current.agentProcess.plan?.summary).toBe("先检查财务和估值");
    expect(queryClient.getQueryData(queryKeys.workflows.analysisHistorySnapshot("600519", "20260826")))
      .toBe(result);
    expect(queryClient.getQueryData<AnalysisPageData>(queryKeys.stock.analysisPage("600519"))?.cached_analysis)
      .toBe(result);
  });

  it("keeps a selected historical snapshot and restores its agent trace", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const historicalWithTrace = {
      ...historicalResult,
      agent_trace: [{
        type: "plan" as const,
        plan: {
          summary: "历史研究思路",
          steps: [],
        },
      }],
    };
    const { result: hook } = renderHook(
      () => useAnalysisWorkflowController({
        code: "600519",
        historyDate: "20260824",
        cachedResult,
        historicalResult: historicalWithTrace,
      }),
      { wrapper: createWrapper(queryClient) },
    );

    await waitFor(() => expect(hook.current.displayResult).toBe(historicalWithTrace));
    expect(hook.current.agentProcess.plan?.summary).toBe("历史研究思路");
  });

  it("keeps a running request alive when the page unmounts", () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const stream = pendingStream();
    streamAnalysis.mockReturnValue(stream);
    const { result: hook, unmount } = renderHook(
      () => useAnalysisWorkflowController({ code: "600519" }),
      { wrapper: createWrapper(queryClient) },
    );

    act(() => { void hook.current.runAnalysis(); });
    expect(hook.current.isAnalyzing).toBe(true);
    unmount();

    expect(stream.detach).not.toHaveBeenCalled();
    expect(stream.cancel).not.toHaveBeenCalled();
    expect(useAnalysisStore.getState().isAnalyzing).toBe(true);
  });

  it("keeps a running request alive across an in-place history route change", () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const stream = pendingStream();
    streamAnalysis.mockReturnValue(stream);
    const { result: hook, rerender } = renderHook(
      ({ code, date }) => useAnalysisWorkflowController({ code, historyDate: date }),
      {
        initialProps: { code: "600519", date: "" },
        wrapper: createWrapper(queryClient),
      },
    );

    act(() => { void hook.current.runAnalysis(); });
    rerender({ code: "600519", date: "20260824" });
    expect(stream.detach).not.toHaveBeenCalled();
    expect(stream.cancel).not.toHaveBeenCalled();
    expect(useAnalysisStore.getState().isAnalyzing).toBe(true);
  });

  it("waits for explicit cancellation and reports the confirmed outcome", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    let resolveCancel: ((value: "cancelled") => void) | undefined;
    let rejectStream: ((error: Error) => void) | undefined;
    const stream = {
      promise: new Promise<AnalysisResult>((_resolve, reject) => { rejectStream = reject; }),
      started: Promise.resolve({ job: { id: "job" }, attached: false }),
      cancel: vi.fn(() => new Promise<"cancelled">((resolve) => {
        resolveCancel = (value) => {
          rejectStream?.(new Error("已取消"));
          resolve(value);
        };
      })),
      detach: vi.fn(),
    };
    streamAnalysis.mockReturnValue(stream);
    const onCancelled = vi.fn();
    const { result: hook } = renderHook(
      () => useAnalysisWorkflowController({ code: "600519", onCancelled }),
      { wrapper: createWrapper(queryClient) },
    );

    act(() => { void hook.current.runAnalysis(); });
    let cancellation: Promise<unknown> | undefined;
    act(() => { cancellation = hook.current.cancelAnalysis(); });
    expect(hook.current.isCancelling).toBe(true);
    expect(onCancelled).not.toHaveBeenCalled();

    await act(async () => {
      resolveCancel?.("cancelled");
      await cancellation;
    });
    expect(onCancelled).toHaveBeenCalledWith("cancelled");
  });

  it("does not let an old controller clear a newer run", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    let resolveOld: ((value: AnalysisResult) => void) | undefined;
    const oldStream = {
      promise: new Promise<AnalysisResult>((resolve) => { resolveOld = resolve; }),
      started: Promise.resolve({ job: { id: "job-old" }, attached: false }),
      cancel: vi.fn(),
      detach: vi.fn(),
    };
    const newStream = pendingStream();
    streamAnalysis.mockReturnValueOnce(oldStream).mockReturnValueOnce(newStream);
    const first = renderHook(
      () => useAnalysisWorkflowController({ code: "600519" }),
      { wrapper: createWrapper(queryClient) },
    );
    act(() => { void first.result.current.runAnalysis(); });
    first.unmount();

    const second = renderHook(
      () => useAnalysisWorkflowController({ code: "000001" }),
      { wrapper: createWrapper(queryClient) },
    );
    act(() => { void second.result.current.runAnalysis(); });
    await act(async () => { resolveOld?.(result); await Promise.resolve(); });

    expect(second.result.current.isAnalyzing).toBe(true);
    expect(useAnalysisStore.getState().currentCode).toBe("000001");
    expect(queryClient.getQueryData(queryKeys.workflows.analysisHistorySnapshot("600519", "20260826")))
      .toBe(result);
    second.unmount();
  });
  it.each(["cancelled", "detached"] as const)("settles %s without showing a cached or late result", async (outcome) => {
    const queryClient = new QueryClient();
    const test = controlledStream();
    const onSuccess = vi.fn();
    const { result: hook, rerender } = renderHook(
      ({ cached }) => useAnalysisWorkflowController({ code: "600519", cachedResult: cached, onSuccess }),
      { initialProps: { cached: cachedResult }, wrapper: createWrapper(queryClient) },
    );
    let run!: ReturnType<typeof hook.current.runAnalysis>;
    act(() => { run = hook.current.runAnalysis(); sendRunningProgress(test.progress); });
    let cancellation!: ReturnType<typeof hook.current.cancelAnalysis>;
    act(() => { cancellation = hook.current.cancelAnalysis(); });
    expect(hook.current.isAnalyzing).toBe(true);
    expect(hook.current.isCancelling).toBe(true);
    expect(hook.current.agentProcess.toolCalls[0].isExecuting).toBe(true);
    await act(async () => { test.acknowledge(outcome); await cancellation; });
    expect(hook.current.isAnalyzing).toBe(false);
    expect(hook.current.isCancelling).toBe(false);
    expect(hook.current.agentProcess.termination).toBe(outcome);
    expect(hook.current.agentProcess.toolCalls[0]).toMatchObject({ isExecuting: false, isCancelled: true });
    expect(hook.current.displayResult).toBeNull();
    await act(async () => {
      test.progress({ type: "stage_started", total_stages: 3,
        stage: { stage: 3, name: "迟到阶段", status: "started" } });
      test.progress({ type: "complete", total_stages: 3, result });
      test.resolve(result);
      await run;
    });
    rerender({ cached: result });
    expect(hook.current.stages[2]).toBeNull();
    expect(hook.current.agentProcess.termination).toBe(outcome);
    expect(hook.current.result).toBeNull();
    expect(hook.current.displayResult).toBeNull();
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("keeps the stream alive when cancellation reports completed before the result arrives", async () => {
    const test = controlledStream();
    const onSuccess = vi.fn();
    const { result: hook } = renderHook(
      () => useAnalysisWorkflowController({ code: "600519", onSuccess }),
      { wrapper: createWrapper(new QueryClient()) },
    );
    let run!: ReturnType<typeof hook.current.runAnalysis>;
    act(() => { run = hook.current.runAnalysis(); });
    let cancellation!: ReturnType<typeof hook.current.cancelAnalysis>;
    act(() => { cancellation = hook.current.cancelAnalysis(); });
    await act(async () => { test.acknowledge("completed"); await cancellation; });
    expect(hook.current.isAnalyzing).toBe(true);
    expect(useAnalysisStore.getState().activeStream).toBe(test.stream);
    await act(async () => { test.resolve(result); await run; });
    expect(hook.current.displayResult).toBe(result);
    expect(hook.current.isAnalyzing).toBe(false);
    expect(hook.current.isCancelling).toBe(false);
    expect(hook.current.agentProcess.termination).toBeUndefined();
    expect(onSuccess).toHaveBeenCalledWith(result);
  });

  it("does not overwrite a completed result with a late cancellation acknowledgement", async () => {
    const test = controlledStream();
    const { result: hook } = renderHook(
      () => useAnalysisWorkflowController({ code: "600519" }),
      { wrapper: createWrapper(new QueryClient()) },
    );
    let run!: ReturnType<typeof hook.current.runAnalysis>;
    act(() => { run = hook.current.runAnalysis(); });
    let cancellation!: ReturnType<typeof hook.current.cancelAnalysis>;
    act(() => { cancellation = hook.current.cancelAnalysis(); });
    await act(async () => { test.resolve(result); await run; });
    await act(async () => { test.acknowledge("cancelled"); await cancellation; });
    expect(hook.current.displayResult).toBe(result);
    expect(hook.current.agentProcess.termination).toBeUndefined();
  });

  it("keeps a failed cancellation retryable without turning research into a failure", async () => {
    const test = controlledStream();
    const onError = vi.fn();
    const { result: hook } = renderHook(
      () => useAnalysisWorkflowController({ code: "600519", onError }),
      { wrapper: createWrapper(new QueryClient()) },
    );
    act(() => { void hook.current.runAnalysis(); sendRunningProgress(test.progress); });
    let cancellation!: ReturnType<typeof hook.current.cancelAnalysis>;
    act(() => { cancellation = hook.current.cancelAnalysis(); });
    await act(async () => { test.rejectCancel(new Error("取消接口暂时失败")); await cancellation; });
    expect(hook.current.isAnalyzing).toBe(true);
    expect(hook.current.isCancelling).toBe(false);
    expect(hook.current.analysisError).toBeNull();
    expect(hook.current.agentProcess.toolCalls[0].isExecuting).toBe(true);
    expect(onError).toHaveBeenCalledWith(expect.objectContaining({ message: "取消接口暂时失败" }));
    act(() => { cancellation = hook.current.cancelAnalysis(); });
    await act(async () => { test.acknowledge("cancelled"); await cancellation; });
    expect(test.stream.cancel).toHaveBeenCalledTimes(2);
    expect(hook.current.agentProcess.termination).toBe("cancelled");
  });

  it("can restart immediately after cancellation while the old promise is pending", async () => {
    const old = controlledStream();
    const next = controlledStream();
    const { result: hook } = renderHook(
      () => useAnalysisWorkflowController({ code: "600519" }),
      { wrapper: createWrapper(new QueryClient()) },
    );
    let oldRun!: ReturnType<typeof hook.current.runAnalysis>;
    act(() => { oldRun = hook.current.runAnalysis(); });
    let cancellation!: ReturnType<typeof hook.current.cancelAnalysis>;
    act(() => { cancellation = hook.current.cancelAnalysis(); });
    await act(async () => { old.acknowledge("cancelled"); await cancellation; });
    let nextRun!: ReturnType<typeof hook.current.runAnalysis>;
    act(() => { nextRun = hook.current.runAnalysis(); });
    expect(streamAnalysis).toHaveBeenCalledTimes(2);
    const active = useAnalysisStore.getState().activeRun;
    await act(async () => { old.reject(new Error("已取消")); await oldRun; });
    expect(useAnalysisStore.getState().activeRun).toBe(active);
    expect(useAnalysisStore.getState().activeStream).toBe(next.stream);
    expect(hook.current.isAnalyzing).toBe(true);
    await act(async () => { next.resolve(result); await nextRun; });
    expect(hook.current.displayResult).toBe(result);
  });

  it("handles server cancellation before the DELETE acknowledgement and ignores late progress", async () => {
    const test = controlledStream();
    const onError = vi.fn();
    const { result: hook } = renderHook(
      () => useAnalysisWorkflowController({ code: "600519", onError }),
      { wrapper: createWrapper(new QueryClient()) },
    );
    let run!: ReturnType<typeof hook.current.runAnalysis>;
    act(() => { run = hook.current.runAnalysis(); sendRunningProgress(test.progress); });
    let cancellation!: ReturnType<typeof hook.current.cancelAnalysis>;
    act(() => { cancellation = hook.current.cancelAnalysis(); });
    await act(async () => {
      test.progress({ type: "error", total_stages: 3, cancelled: true, error: "个股研究已取消" });
      sendRunningProgress(test.progress);
      test.reject(new Error("个股研究已取消"));
      await run;
    });
    expect(hook.current.isAnalyzing).toBe(false);
    expect(hook.current.agentProcess.termination).toBe("cancelled");
    expect(hook.current.agentProcess.toolCalls[0].isExecuting).toBe(false);
    expect(onError).not.toHaveBeenCalled();
    await act(async () => { test.acknowledge("cancelled"); await cancellation; });
    expect(hook.current.analysisError).toBeNull();
  });

  it.each(["已取消", "已停止等待", "上游模型失败"])("settles active tools when a stream rejects: %s", async (message) => {
    const test = controlledStream();
    const { result: hook } = renderHook(
      () => useAnalysisWorkflowController({ code: "600519" }),
      { wrapper: createWrapper(new QueryClient()) },
    );
    let run!: ReturnType<typeof hook.current.runAnalysis>;
    act(() => { run = hook.current.runAnalysis(); sendRunningProgress(test.progress); });
    await act(async () => { test.reject(new Error(message)); await run; });
    expect(hook.current.isAnalyzing).toBe(false);
    expect(hook.current.agentProcess.termination).toBe(message === "已取消" ? "cancelled" : message === "已停止等待" ? "detached" : "failed");
    expect(hook.current.agentProcess.toolCalls[0].isExecuting).toBe(false);
    expect(hook.current.analysisError).toBe(message === "上游模型失败" ? message : null);
  });

  it("does not start duplicate streams for the same code from separate page controllers", () => {
    streamAnalysis.mockReturnValue(pendingStream());
    const wrapper = createWrapper(new QueryClient());
    const first = renderHook(() => useAnalysisWorkflowController({ code: "600519" }), { wrapper });
    const second = renderHook(() => useAnalysisWorkflowController({ code: "600519" }), { wrapper });
    act(() => { void first.result.current.runAnalysis(); void second.result.current.runAnalysis(); });
    expect(streamAnalysis).toHaveBeenCalledTimes(1);
    expect(first.result.current.isAnalyzing).toBe(true);
    expect(second.result.current.isAnalyzing).toBe(true);
  });

  it("still allows explicitly opening a historical report after cancelling current research", async () => {
    const test = controlledStream();
    const { result: hook, rerender } = renderHook(
      ({ date }) => useAnalysisWorkflowController({ code: "600519", historyDate: date, cachedResult, historicalResult }),
      { initialProps: { date: "" }, wrapper: createWrapper(new QueryClient()) },
    );
    act(() => { void hook.current.runAnalysis(); });
    let cancellation!: ReturnType<typeof hook.current.cancelAnalysis>;
    act(() => { cancellation = hook.current.cancelAnalysis(); });
    await act(async () => { test.acknowledge("cancelled"); await cancellation; });
    expect(hook.current.displayResult).toBeNull();
    rerender({ date: "20260824" });
    expect(hook.current.displayResult).toBe(historicalResult);
    rerender({ date: "" });
    expect(hook.current.displayResult).toBeNull();
    expect(hook.current.agentProcess.termination).toBe("cancelled");
  });

  it("discards an intermediate complete event if the server subsequently confirms cancellation", async () => {
    const test = controlledStream();
    const onSuccess = vi.fn();
    const { result: hook } = renderHook(
      () => useAnalysisWorkflowController({ code: "600519", onSuccess }),
      { wrapper: createWrapper(new QueryClient()) },
    );
    let run!: ReturnType<typeof hook.current.runAnalysis>;
    act(() => { run = hook.current.runAnalysis(); });
    let cancellation!: ReturnType<typeof hook.current.cancelAnalysis>;
    act(() => {
      cancellation = hook.current.cancelAnalysis();
      test.progress({ type: "complete", total_stages: 3, result });
    });
    await act(async () => { test.acknowledge("cancelled"); await cancellation; });
    await act(async () => { test.reject(new Error("已取消")); await run; });
    expect(hook.current.displayResult).toBeNull();
    expect(hook.current.agentProcess.termination).toBe("cancelled");
    expect(onSuccess).not.toHaveBeenCalled();
  });

});
