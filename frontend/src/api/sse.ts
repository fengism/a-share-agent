import type { AnalysisResult, IndustryChainResult } from "../types/stock";
import { getToken, notifyUnauthorized } from "./authToken";

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

/**
 * Stream a Server-Sent-Events endpoint via fetch (instead of EventSource) so we
 * can attach the Bearer token — the backend binds the per-user config from it.
 * Each `data:` payload is JSON-parsed and passed to onData. Resolves when the
 * stream ends; rejects on network/HTTP error (401 also drops local auth).
 */
async function readSSE(
  url: string,
  onData: (obj: unknown) => void,
  signal: AbortSignal,
): Promise<void> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(url, { method: "GET", headers, signal });
  if (!res.ok) {
    if (res.status === 401 && token) notifyUnauthorized();
    const errData = await res.json().catch(() => ({}));
    throw new Error((errData as { detail?: string }).detail || `SSE error: ${res.status}`);
  }
  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed.startsWith("data:")) continue; // ignore `event:` / comment lines
      const jsonStr = trimmed.replace(/^data:\s*/, "");
      if (!jsonStr) continue;
      try {
        onData(JSON.parse(jsonStr));
      } catch (err) {
        if (isDev) console.error("[SSE] JSON解析失败:", jsonStr, err);
      }
    }
  }
}

export function streamAnalysis(
  code: string,
  onProgress: ProgressHandler,
): { promise: Promise<AnalysisResult>; cancel: () => void } {
  const controller = new AbortController();
  const url = `/api/analysis/${code}/stream`;
  if (isDev) console.log(`[SSE] 连接: ${url}`);

  const promise = new Promise<AnalysisResult>((resolve, reject) => {
    let settled = false;
    readSSE(
      url,
      (obj) => {
        const data = obj as AnalysisProgress;
        onProgress(data);
        if ((data.type === "complete" || data.type === "cached") && data.result) {
          settled = true;
          controller.abort();
          resolve(data.result);
        } else if (data.type === "error") {
          settled = true;
          controller.abort();
          reject(new Error(data.error || "分析失败"));
        }
      },
      controller.signal,
    )
      .then(() => {
        if (!settled) reject(new Error("连接已结束但未返回结果"));
      })
      .catch((err: Error) => {
        if (settled) return; // aborted by us after resolving/rejecting
        if (err.name === "AbortError") reject(new Error("已取消"));
        else reject(err instanceof Error ? err : new Error(String(err)));
      });
  });

  return { promise, cancel: () => controller.abort() };
}

// ── 产业链分析 SSE ──

export interface IndustryChainProgress {
  type: "stage_started" | "stage_completed" | "complete" | "error";
  stage?: string;
  message?: string;
  result?: IndustryChainResult | null;
}

export type IndustryChainProgressHandler = (event: IndustryChainProgress) => void;

export function streamIndustryChain(
  name: string,
  onProgress: IndustryChainProgressHandler,
): { promise: Promise<IndustryChainResult>; cancel: () => void } {
  const controller = new AbortController();
  const url = `/api/industry-chain/${encodeURIComponent(name)}/stream`;

  const promise = new Promise<IndustryChainResult>((resolve, reject) => {
    let settled = false;
    readSSE(
      url,
      (obj) => {
        const data = obj as IndustryChainProgress;
        onProgress(data);
        if (data.type === "complete" && data.result) {
          settled = true;
          controller.abort();
          resolve(data.result);
        } else if (data.type === "error") {
          settled = true;
          controller.abort();
          reject(new Error(data.message || "分析失败"));
        }
      },
      controller.signal,
    )
      .then(() => {
        if (!settled) reject(new Error("连接已结束但未返回结果"));
      })
      .catch((err: Error) => {
        if (settled) return;
        if (err.name === "AbortError") reject(new Error("已取消"));
        else reject(err instanceof Error ? err : new Error(String(err)));
      });
  });

  return { promise, cancel: () => controller.abort() };
}
