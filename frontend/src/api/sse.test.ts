import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./client", () => ({
  apiDelete: vi.fn(),
  apiPost: vi.fn(),
}));

import { apiDelete, apiPost } from "./client";
import { streamAnalysis, streamDailyReview, streamIndustryChain } from "./sse";

function sseResponse(content: string): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      controller.enqueue(encoder.encode(content));
      controller.close();
    },
  });
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

function mockSubmission(jobId = "job-1") {
  vi.mocked(apiPost).mockResolvedValue({ job: { id: jobId }, attached: false });
}

describe("durable workflow SSE", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(apiDelete).mockResolvedValue({ status: "cancelled" });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("creates an analysis job before streaming its persisted events", async () => {
    mockSubmission();
    const result = { stock_code: "600519" };
    const fetchMock = vi.fn(async () => sseResponse(
      `id: 1:1\nevent: complete\ndata: ${JSON.stringify({
        type: "complete",
        total_stages: 7,
        result,
      })}\n\n`,
    ));
    vi.stubGlobal("fetch", fetchMock);
    const progress = vi.fn();

    const stream = streamAnalysis("600519", progress);

    await expect(stream.promise).resolves.toEqual(result);
    expect(apiPost).toHaveBeenCalledWith("/workflows/analysis/600519");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/workflows/job-1/stream",
      expect.objectContaining({ method: "GET", credentials: "include" }),
    );
    expect(progress).toHaveBeenCalledWith(expect.objectContaining({ type: "complete" }));
    expect(apiDelete).not.toHaveBeenCalled();
  });

  it("submits and resolves a durable daily review", async () => {
    mockSubmission("review-job");
    const result = { date: "2026-08-18", quality_status: "complete" };
    const fetchMock = vi.fn(async () => sseResponse(
      `id: 1:1\nevent: complete\ndata: ${JSON.stringify({ type: "complete", result })}\n\n`,
    ));
    vi.stubGlobal("fetch", fetchMock);
    const progress = vi.fn();

    const stream = streamDailyReview({ date: "2026-08-18", force: true }, progress);

    await expect(stream.promise).resolves.toEqual(result);
    expect(apiPost).toHaveBeenCalledWith("/workflows/daily-review", { date: "2026-08-18", force: true });
    expect(progress).toHaveBeenCalledWith(expect.objectContaining({ type: "complete" }));
  });

  it("reconnects with the last persisted event cursor", async () => {
    vi.useFakeTimers();
    mockSubmission();
    const result = { name: "人工智能" };
    const progress = vi.fn();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(sseResponse(
        "id: 1:1\nevent: stage_started\ndata: {\"type\":\"stage_started\",\"stage\":\"collect\"}\n\n",
      ))
      .mockResolvedValueOnce(sseResponse(
        `id: 1:2\nevent: complete\ndata: ${JSON.stringify({
          type: "complete",
          archive_id: "archive-1",
          archive_status: "saved",
          quality_status: "degraded",
          warnings: ["证据覆盖不足"],
          result,
        })}\n\n`,
      ));
    vi.stubGlobal("fetch", fetchMock);

    const stream = streamIndustryChain("人工智能", progress, {
      region: "china",
      time_range: "one_year",
      company_scope: "a_share",
    }, { force: true });
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    await vi.advanceTimersByTimeAsync(250);

    await expect(stream.promise).resolves.toEqual({
      ...result,
      archive_id: "archive-1",
      archive_status: "saved",
      quality_status: "degraded",
      warnings: ["证据覆盖不足"],
    });
    expect(apiPost).toHaveBeenCalledWith(
      `/workflows/industry-chain/${encodeURIComponent("人工智能")}?force=true`,
      {
        region: "china",
        time_range: "one_year",
        company_scope: "a_share",
      },
    );
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const reconnectHeaders = fetchMock.mock.calls[1][1]?.headers as Record<string, string>;
    expect(reconnectHeaders["Last-Event-ID"]).toBe("1:1");
    expect(progress.mock.calls.map(([event]) => event.type)).toEqual(["stage_started", "complete"]);
  });

  it("cancels the remote job before aborting the active stream", async () => {
    mockSubmission();
    const lifecycle: string[] = [];
    let resolveDelete: (() => void) | undefined;
    vi.mocked(apiDelete).mockImplementation(() => {
      lifecycle.push("delete");
      return new Promise((resolve) => {
        resolveDelete = () => resolve({ status: "cancelled" });
      });
    });
    const fetchMock = vi.fn((_url: string, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => {
        lifecycle.push("abort");
        reject(new DOMException("aborted", "AbortError"));
      }, { once: true });
    }));
    vi.stubGlobal("fetch", fetchMock);

    const stream = streamAnalysis("600519", vi.fn());
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    const cancellation = stream.cancel();
    await vi.waitFor(() => expect(apiDelete).toHaveBeenCalledWith("/workflows/job-1"));

    expect(lifecycle).toEqual(["delete"]);
    resolveDelete?.();
    await expect(cancellation).resolves.toBe("cancelled");
    await expect(stream.promise).rejects.toThrow("已取消");
    expect(lifecycle).toEqual(["delete", "abort"]);
  });

  it("detaches from an attached job without cancelling the shared task", async () => {
    vi.mocked(apiPost).mockResolvedValue({ job: { id: "shared-job" }, attached: true });
    const fetchMock = vi.fn((_url: string, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")), { once: true });
    }));
    vi.stubGlobal("fetch", fetchMock);

    const stream = streamAnalysis("600519", vi.fn());
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    await expect(stream.cancel()).resolves.toBe("detached");
    await expect(stream.promise).rejects.toThrow("已停止等待");
    expect(apiDelete).not.toHaveBeenCalled();
  });

  it("sends force refresh through the analysis submission query", async () => {
    mockSubmission();
    const result = { stock_code: "600519" };
    vi.stubGlobal("fetch", vi.fn(async () => sseResponse(
      `id: 1:1\ndata: ${JSON.stringify({ type: "complete", result })}\n\n`,
    )));

    const stream = streamAnalysis("600519", vi.fn(), { force: true });

    await expect(stream.promise).resolves.toEqual(result);
    expect(apiPost).toHaveBeenCalledWith("/workflows/analysis/600519?force=true");
  });

  it("reports completion when the server wins a cancellation race", async () => {
    mockSubmission();
    vi.mocked(apiDelete).mockResolvedValue({ status: "succeeded" });
    vi.stubGlobal("fetch", vi.fn((_url: string, init?: RequestInit) => new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")), { once: true });
    })));
    const stream = streamAnalysis("600519", vi.fn());
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(1));

    await expect(stream.cancel()).resolves.toBe("completed");
    expect(apiDelete).toHaveBeenCalledWith("/workflows/job-1");
  });

  it("keeps cancellation authoritative when a complete event races with it", async () => {
    mockSubmission();
    let resolveDelete: (() => void) | undefined;
    let resolveFetch: ((response: Response) => void) | undefined;
    vi.mocked(apiDelete).mockImplementation(() => new Promise((resolve) => {
      resolveDelete = () => resolve({ status: "cancelled" });
    }));
    const fetchMock = vi.fn(() => new Promise<Response>((resolve) => {
      resolveFetch = resolve;
    }));
    vi.stubGlobal("fetch", fetchMock);
    const progress = vi.fn();
    const stream = streamAnalysis("600519", progress);
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));

    const cancellation = stream.cancel();
    resolveFetch?.(sseResponse(
      `id: 1:1\nevent: complete\ndata: ${JSON.stringify({
        type: "complete",
        total_stages: 7,
        result: { stock_code: "600519" },
      })}\n\n`,
    ));
    await vi.waitFor(() => expect(progress).toHaveBeenCalledWith(expect.objectContaining({ type: "complete" })));
    resolveDelete?.();

    await expect(cancellation).resolves.toBe("cancelled");
    await expect(stream.promise).rejects.toThrow("已取消");
  });
});
