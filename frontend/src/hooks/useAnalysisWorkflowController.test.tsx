import type { PropsWithChildren } from "react";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";
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
});
