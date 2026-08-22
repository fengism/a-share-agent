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
  type: "stage_started" | "stage_completed" | "stage_failed" | "complete" | "error" | "cached";
  stage?: AnalysisStage | null;
  total_stages: number;
  result?: AnalysisResult | null;
  error?: string | null;
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
  if (dataLines.length === 0) return { id, stop: false };

  const payload = dataLines.join("\n");
  try {
    return { id, stop: onData(JSON.parse(payload)) === true };
  } catch (error) {
    if (isDev) console.error("[SSE] JSON解析失败:", payload, error);
    return { id, stop: false };
  }
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
    if (frame.id !== undefined) currentEventId = frame.id;
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

function streamWorkflow<Result, Progress>(
  submissionPath: string,
  onProgress: (event: Progress) => void,
  terminalFromEvent: (event: Progress) => WorkflowTerminal<Result> | null,
  submissionBody?: unknown,
): { promise: Promise<Result>; cancel: () => void } {
  const streamController = new AbortController();
  let jobId: string | null = null;
  let cancelRequested = false;
  let cancellationPromise: Promise<void> | null = null;

  const requestCancellation = (): Promise<void> => {
    if (!jobId) return Promise.resolve();
    if (!cancellationPromise) {
      cancellationPromise = apiDelete(`/workflows/${encodeURIComponent(jobId)}`)
        .then(() => undefined)
        .finally(() => streamController.abort());
    }
    return cancellationPromise;
  };

  const promise = (async () => {
    let terminal: WorkflowTerminal<Result> | null = null;
    try {
      const submission = submissionBody === undefined
        ? await apiPost<WorkflowSubmission>(submissionPath)
        : await apiPost<WorkflowSubmission>(submissionPath, submissionBody);
      jobId = submission.job.id;
      if (cancelRequested) {
        await requestCancellation();
        throw new Error("已取消");
      }

      const streamUrl = `/api/workflows/${encodeURIComponent(jobId)}/stream`;
      let lastEventId: string | undefined;
      let reconnectAttempts = 0;
      while (!terminal) {
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
            lastEventId,
          );
        } catch (error) {
          if (cancelRequested || isAbortError(error)) throw error;
          if (error instanceof SSERequestError && !error.retryable) throw error;
          if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) throw error;
        }
        if (terminal) break;
        if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
          throw new Error("连接已结束但未返回结果");
        }
        const delay = RECONNECT_BASE_DELAY_MS * (2 ** reconnectAttempts);
        reconnectAttempts += 1;
        await waitForReconnect(delay, streamController.signal);
      }

      if (cancelRequested) {
        await requestCancellation();
        throw new Error("已取消");
      }
      const completed = terminal as WorkflowTerminal<Result>;
      if (completed.status === "rejected") throw completed.error;
      return completed.result;
    } catch (error) {
      if (cancelRequested) {
        await requestCancellation();
        throw new Error("已取消");
      }
      if (isAbortError(error)) throw new Error("已取消");
      throw error instanceof Error ? error : new Error(String(error));
    }
  })();

  const cancel = () => {
    if (cancelRequested) return;
    cancelRequested = true;
    if (jobId) void requestCancellation().catch(() => undefined);
  };
  return { promise, cancel };
}

export function streamAnalysis(
  code: string,
  onProgress: ProgressHandler,
): { promise: Promise<AnalysisResult>; cancel: () => void } {
  return streamWorkflow(
    `/workflows/analysis/${encodeURIComponent(code)}`,
    onProgress,
    (event) => {
      if ((event.type === "complete" || event.type === "cached") && event.result) {
        return { status: "resolved", result: event.result };
      }
      if (event.type === "error") {
        return { status: "rejected", error: new Error(event.error || "分析失败") };
      }
      return null;
    },
  );
}

// ── 产业链分析 SSE ──

export interface IndustryChainProgress {
  type: "stage_started" | "stage_completed" | "agent_event" | "complete" | "error";
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
  type: "stage_started" | "stage_completed" | "complete" | "error";
  stage?: string;
  message?: string;
  result?: DailyReviewResult;
}

export function streamDailyReview(
  request: DailyReviewRequest,
  onProgress: (event: DailyReviewProgress) => void,
): { promise: Promise<DailyReviewResult>; cancel: () => void } {
  return streamWorkflow(
    "/workflows/daily-review",
    onProgress,
    (event) => {
      if (event.type === "complete" && event.result) return { status: "resolved", result: event.result };
      if (event.type === "error") return { status: "rejected", error: new Error(event.message || "每日复盘生成失败") };
      return null;
    },
    request,
  );
}

export function streamIndustryChain(
  name: string,
  onProgress: IndustryChainProgressHandler,
  scope?: IndustryChainResearchScope,
): { promise: Promise<IndustryChainResult>; cancel: () => void } {
  return streamWorkflow(
    `/workflows/industry-chain/${encodeURIComponent(name)}`,
    onProgress,
    (event) => {
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
    },
    scope,
  );
}


export interface ScreenerStrategyProgress {
  type: "progress" | "complete" | "error";
  completed?: number;
  total?: number;
  matched?: number;
  failed?: number;
  result?: ScreenerStrategyResult;
  message?: string;
}

export function streamScreenerStrategy(
  request: ScreenerStrategyRequest,
  onProgress: (event: ScreenerStrategyProgress) => void,
): { promise: Promise<ScreenerStrategyResult>; cancel: () => void } {
  return streamWorkflow(
    "/workflows/screener-strategy",
    onProgress,
    (event) => {
      if (event.type === "complete" && event.result) return { status: "resolved", result: event.result };
      if (event.type === "error") return { status: "rejected", error: new Error(event.message || "策略选股失败") };
      return null;
    },
    request,
  );
}
