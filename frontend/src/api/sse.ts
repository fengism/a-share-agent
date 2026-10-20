import type {
  AnalysisResult,
  IndustryChainResearchScope,
  IndustryChainResult,
  ScreenerStrategyRequest,
  ScreenerStrategyResult,
} from "../types/stock";
import type { ChatStreamDelta } from "../types/chat";
import type { DailyReviewRequest, DailyReviewResult } from "../types/dailyReview";
import { getToken, notifyUnauthorized } from "./authToken";
import { apiDelete, apiPost } from "./client";
import { parseApiError } from "./errors";

export interface AnalysisStage {
  stage: number;
  name: string;
  status: "started" | "completed" | "failed";
  detail?: string | null;
  duration_ms?: number | null;
}

export interface AnalysisProgress {
  type: "stage_started" | "stage_completed" | "stage_failed" | "agent_event" | "complete" | "error" | "cached";
  stage?: AnalysisStage | null;
  total_stages: number;
  agent_event?: ChatStreamDelta | null;
  result?: AnalysisResult | null;
  error?: string | null;
  cancelled?: boolean;
}

export type ProgressHandler = (event: AnalysisProgress) => void;

const isDev = import.meta.env.DEV;
const MAX_RECONNECT_ATTEMPTS = 4;
const RECONNECT_BASE_DELAY_MS = 250;

interface WorkflowSubmission {
  job: { id: string };
  attached: boolean;
}

class SSERequestError extends Error {
  readonly retryable: boolean;

  constructor(message: string, status: number) {
    super(message);
    this.name = "SSERequestError";
    this.retryable = status === 429 || status >= 500;
  }
}

interface SSEFrameResult {
  id?: string;
  stop: boolean;
  handled: boolean;
}

class SSEPayloadError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SSEPayloadError";
  }
}

function parseSSEFrame(
  lines: string[],
  onData: (obj: unknown) => boolean | void,
): SSEFrameResult {
  let id: string | undefined;
  const dataLines: string[] = [];
  for (const line of lines) {
    if (!line || line.startsWith(":")) continue;
    const separator = line.indexOf(":");
    const field = separator === -1 ? line : line.slice(0, separator);
    const rawValue = separator === -1 ? "" : line.slice(separator + 1);
    const value = rawValue.startsWith(" ") ? rawValue.slice(1) : rawValue;
    if (field === "id" && !value.includes("\0")) id = value;
    if (field === "data") dataLines.push(value);
  }
  if (dataLines.length === 0) return { id, stop: false, handled: false };

  const payload = dataLines.join("\n");
  let parsed: unknown;
  try {
    parsed = JSON.parse(payload);
  } catch (error) {
    if (isDev) console.error("[SSE] JSON解析失败:", payload, error);
    throw new SSEPayloadError("任务事件格式无效");
  }
  return { id, stop: onData(parsed) === true, handled: true };
}

/**
 * Stream a Server-Sent-Events endpoint via fetch so cookie credentials, aborts,
 * and streamed response parsing share the same lifecycle.
 * Each `data:` payload is JSON-parsed and passed to onData. Resolves when the
 * stream ends; rejects on network/HTTP error (401 also drops local auth).
 */
async function readSSE(
  url: string,
  onData: (obj: unknown) => boolean | void,
  signal: AbortSignal,
  onCursor: (id: string) => void,
  onProgress: () => void,
  lastEventId?: string,
): Promise<string | undefined> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (lastEventId) headers["Last-Event-ID"] = lastEventId;

  const res = await fetch(url, {
    method: "GET",
    headers,
    signal,
    credentials: "include",
  });
  if (!res.ok) {
    if (res.status === 401) notifyUnauthorized();
    const error = parseApiError(
      await res.json().catch(() => ({})),
      `SSE error: ${res.status}`,
    );
    throw new SSERequestError(error.message, res.status);
  }
  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";
  let frameLines: string[] = [];
  let currentEventId = lastEventId;

  const dispatchFrame = (): boolean => {
    const frame = parseSSEFrame(frameLines, onData);
    frameLines = [];
    if (frame.handled) {
      onProgress();
      if (frame.id !== undefined) {
        currentEventId = frame.id;
        onCursor(frame.id);
      }
    }
    return frame.stop;
  };

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value, { stream: !done });
    let newline = buffer.indexOf("\n");
    while (newline !== -1) {
      const rawLine = buffer.slice(0, newline);
      buffer = buffer.slice(newline + 1);
      const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
      if (line === "") {
        if (dispatchFrame()) {
          await reader.cancel();
          return currentEventId;
        }
      } else {
        frameLines.push(line);
      }
      newline = buffer.indexOf("\n");
    }
    if (done) break;
  }
  if (buffer) frameLines.push(buffer.endsWith("\r") ? buffer.slice(0, -1) : buffer);
  if (frameLines.length > 0) dispatchFrame();
  return currentEventId;
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException
    ? error.name === "AbortError"
    : error instanceof Error && error.name === "AbortError";
}

function waitForReconnect(delayMs: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) {
      reject(new DOMException("aborted", "AbortError"));
      return;
    }
    const timer = window.setTimeout(resolve, delayMs);
    signal.addEventListener("abort", () => {
      window.clearTimeout(timer);
      reject(new DOMException("aborted", "AbortError"));
    }, { once: true });
  });
}

type WorkflowTerminal<Result> =
  | { status: "resolved"; result: Result }
  | { status: "rejected"; error: Error };

export type WorkflowCancelResult = "cancelled" | "detached" | "completed";

export interface WorkflowStream<Result> {
  promise: Promise<Result>;
  started: Promise<WorkflowSubmission>;
  cancel: () => Promise<WorkflowCancelResult>;
  detach: () => void;
}

interface WorkflowSubmissionOptions {
  body?: unknown;
  query?: Record<string, string | number | boolean>;
  existingSubmission?: WorkflowSubmission;
}

function submissionPathWithQuery(
  path: string,
  query?: Record<string, string | number | boolean>,
): string {
  if (!query) return path;
  const params = new URLSearchParams();
  Object.entries(query).forEach(([key, value]) => params.set(key, String(value)));
  const serialized = params.toString();
  return serialized ? `${path}?${serialized}` : path;
}

function streamWorkflow<Result, Progress>(
  submissionPath: string,
  onProgress: (event: Progress) => void,
  terminalFromEvent: (event: Progress) => WorkflowTerminal<Result> | null,
  options: WorkflowSubmissionOptions = {},
): WorkflowStream<Result> {
  const streamController = new AbortController();
  const submitPath = submissionPathWithQuery(submissionPath, options.query);
  let jobId: string | null = null;
  let attached = false;
  let cancelRequested = false;
  let detached = false;
  let cancellationPromise: Promise<WorkflowCancelResult> | null = null;
  let resolveSubmission: () => void = () => undefined;
  const submissionReady = new Promise<void>((resolve) => {
    resolveSubmission = resolve;
  });
  const markSubmissionReady = () => {
    resolveSubmission();
    resolveSubmission = () => undefined;
  };

  const detach = () => {
    detached = true;
    streamController.abort();
  };

  const requestCancellation = async (): Promise<WorkflowCancelResult> => {
    if (cancellationPromise) return cancellationPromise;
    cancellationPromise = (async () => {
      await submissionReady;
      if (!jobId || attached) {
        detach();
        return "detached";
      }
      try {
        const response = await apiDelete<{ status: string }>(`/workflows/${encodeURIComponent(jobId)}`);
        if (response.status === "succeeded") {
          cancelRequested = false;
          return "completed";
        }
        if (response.status !== "cancelled") throw new Error("任务取消未被服务端确认");
        streamController.abort();
        return "cancelled";
      } catch (error) {
        cancelRequested = false;
        cancellationPromise = null;
        throw error;
      }
    })();
    return cancellationPromise;
  };

  let resolveStarted: ((submission: WorkflowSubmission) => void) | undefined;
  let rejectStarted: ((error: Error) => void) | undefined;
  const started = new Promise<WorkflowSubmission>((resolve, reject) => {
    resolveStarted = resolve;
    rejectStarted = reject;
  });

  const promise = (async () => {
    let terminal: WorkflowTerminal<Result> | null = null;
    try {
      const submission = options.existingSubmission ?? (options.body === undefined
        ? await apiPost<WorkflowSubmission>(submitPath)
        : await apiPost<WorkflowSubmission>(submitPath, options.body));
      jobId = submission.job.id;
      attached = submission.attached;
      resolveStarted?.(submission);
      resolveStarted = undefined;
      rejectStarted = undefined;
      markSubmissionReady();
      if (cancelRequested) {
        const cancellation = await requestCancellation();
        if (cancellation === "completed") cancelRequested = false;
        else throw new Error(cancellation === "detached" ? "已停止等待" : "已取消");
      }

      const streamUrl = `/api/workflows/${encodeURIComponent(jobId)}/stream`;
      let lastEventId: string | undefined;
      let reconnectAttempts = 0;
      while (!terminal) {
        let madeProgress = false;
        try {
          lastEventId = await readSSE(
            streamUrl,
            (obj) => {
              const event = obj as Progress;
              onProgress(event);
              terminal = terminalFromEvent(event);
              return terminal !== null;
            },
            streamController.signal,
            (id) => {
              lastEventId = id;
            },
            () => {
              madeProgress = true;
              reconnectAttempts = 0;
            },
            lastEventId,
          );
        } catch (error) {
          if (cancelRequested || detached || isAbortError(error)) throw error;
          if (error instanceof SSEPayloadError) throw error;
          if (error instanceof SSERequestError && !error.retryable) throw error;
          if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) throw error;
        }
        if (terminal) break;
        if (!madeProgress && reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
          throw new Error("连接已结束但未返回结果");
        }
        const delay = RECONNECT_BASE_DELAY_MS * (2 ** reconnectAttempts);
        reconnectAttempts += 1;
        await waitForReconnect(delay, streamController.signal);
      }

      if (cancelRequested) {
        const cancellation = await requestCancellation();
        if (cancellation === "completed") cancelRequested = false;
        else throw new Error(cancellation === "detached" ? "已停止等待" : "已取消");
      }
      const completed = terminal as WorkflowTerminal<Result>;
      if (completed.status === "rejected") throw completed.error;
      return completed.result;
    } catch (error) {
      if (rejectStarted) rejectStarted(error instanceof Error ? error : new Error(String(error)));
      resolveStarted = undefined;
      rejectStarted = undefined;
      markSubmissionReady();
      if (cancelRequested) {
        const cancellation = await requestCancellation();
        if (cancellation === "completed") cancelRequested = false;
        else throw new Error(cancellation === "detached" ? "已停止等待" : "已取消");
      }
      if (detached || isAbortError(error)) throw new Error("已停止等待");
      throw error instanceof Error ? error : new Error(String(error));
    }
  })();

  const cancel = async (): Promise<WorkflowCancelResult> => {
    cancelRequested = true;
    return requestCancellation();
  };
  return { promise, started, cancel, detach };
}

export function resumeWorkflow<Result, Progress>(
  jobId: string,
  onProgress: (event: Progress) => void,
  terminalFromEvent: (event: Progress) => WorkflowTerminal<Result> | null,
): WorkflowStream<Result> {
  return streamWorkflow("", onProgress, terminalFromEvent, {
    existingSubmission: { job: { id: jobId }, attached: true },
  });
}

function analysisTerminal(event: AnalysisProgress): WorkflowTerminal<AnalysisResult> | null {
  if ((event.type === "complete" || event.type === "cached") && event.result) {
    return { status: "resolved", result: event.result };
  }
  if (event.type === "error") {
    return { status: "rejected", error: new Error(event.error || "分析失败") };
  }
  return null;
}

export function streamAnalysis(
  code: string,
  onProgress: ProgressHandler,
  options: { force?: boolean } = {},
): WorkflowStream<AnalysisResult> {
  return streamWorkflow(
    `/workflows/analysis/${encodeURIComponent(code)}`,
    onProgress,
    analysisTerminal,
    { query: options.force ? { force: true } : undefined },
  );
}

export function resumeAnalysis(jobId: string, onProgress: ProgressHandler): WorkflowStream<AnalysisResult> {
  return resumeWorkflow(jobId, onProgress, analysisTerminal);
}

// ── 产业链分析 SSE ──

export interface IndustryChainProgress {
  cancelled?: boolean;
  type: "stage_started" | "stage_completed" | "stage_failed" | "agent_event" | "complete" | "error";
  stage?: string;
  message?: string;
  agent_event?: ChatStreamDelta | null;
  result?: IndustryChainResult | null;
  archive_id?: string;
  archive_status?: "none" | "saved" | "failed";
  quality_status?: "complete" | "degraded";
  warnings?: string[];
}

export type IndustryChainProgressHandler = (event: IndustryChainProgress) => void;

export interface DailyReviewProgress {
  type:
    | "stage_started"
    | "stage_completed"
    | "stage_progress"
    | "source_done"
    | "cache_hit"
    | "complete"
    | "error";
  stage?: string;
  message?: string;
  /** 采集阶段：当前完成的数据源名。 */
  source?: string;
  status?: "complete" | "unavailable";
  /** 采集阶段完成计数。 */
  done?: number;
  total?: number;
  /** 采集阶段汇总：源总数与失败数。 */
  sources?: number;
  failed?: number;
  /** 长耗时阶段心跳的已用毫秒。 */
  elapsed_ms?: number;
  generation_status?: "llm" | "fallback";
  result?: DailyReviewResult;
}

export function streamDailyReview(
  request: DailyReviewRequest,
  onProgress: (event: DailyReviewProgress) => void,
): WorkflowStream<DailyReviewResult> {
  return streamWorkflow(
    "/workflows/daily-review",
    onProgress,
    (event) => {
      if (event.type === "complete" && event.result) return { status: "resolved", result: event.result };
      if (event.type === "error") return { status: "rejected", error: new Error(event.message || "每日复盘生成失败") };
      return null;
    },
    { body: request },
  );
}

function industryChainTerminal(
  event: IndustryChainProgress,
): WorkflowTerminal<IndustryChainResult> | null {
  if (event.type === "complete" && event.result) {
    return {
      status: "resolved",
      result: {
        ...event.result,
        archive_id: event.archive_id || event.result.archive_id,
        archive_status: event.archive_status || event.result.archive_status,
        quality_status: event.quality_status || event.result.quality_status,
        warnings: event.warnings || event.result.warnings,
      },
    };
  }
  if (event.type === "error") {
    return { status: "rejected", error: new Error(event.message || "分析失败") };
  }
  return null;
}

export function streamIndustryChain(
  name: string,
  onProgress: IndustryChainProgressHandler,
  scope?: IndustryChainResearchScope,
  options: { force?: boolean } = {},
): WorkflowStream<IndustryChainResult> {
  return streamWorkflow(
    `/workflows/industry-chain/${encodeURIComponent(name)}`,
    onProgress,
    industryChainTerminal,
    {
      body: scope,
      query: options.force ? { force: true } : undefined,
    },
  );
}

export function resumeIndustryChain(
  jobId: string,
  onProgress: IndustryChainProgressHandler,
): WorkflowStream<IndustryChainResult> {
  return resumeWorkflow(jobId, onProgress, industryChainTerminal);
}


export interface ScreenerStrategyProgress {
  type: "progress" | "complete" | "error";
  completed?: number;
  total?: number;
  matched?: number;
  excluded?: number;
  failed?: number;
  result?: ScreenerStrategyResult;
  message?: string;
}

export function streamScreenerStrategy(
  request: ScreenerStrategyRequest,
  onProgress: (event: ScreenerStrategyProgress) => void,
): WorkflowStream<ScreenerStrategyResult> {
  return streamWorkflow(
    "/workflows/screener-strategy",
    onProgress,
    (event) => {
      if (event.type === "complete" && event.result) return { status: "resolved", result: event.result };
      if (event.type === "error") return { status: "rejected", error: new Error(event.message || "策略选股失败") };
      return null;
    },
    { body: request },
  );
}
