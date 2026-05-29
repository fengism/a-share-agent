import type { AnalysisResult } from "../types/stock";

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

export function streamAnalysis(code: string, onProgress: ProgressHandler): {
  promise: Promise<AnalysisResult>;
  cancel: () => void;
} {
  const url = `/api/analysis/${code}/stream`;
  console.log(`[SSE] 连接: ${url}`);
  const eventSource = new EventSource(url);

  let resolveResult: (result: AnalysisResult) => void;
  let rejectResult: (error: Error) => void;

  const promise = new Promise<AnalysisResult>((resolve, reject) => {
    resolveResult = resolve;
    rejectResult = reject;
  });

  const eventTypes = ["stage_started", "stage_completed", "stage_failed", "complete", "error", "cached"] as const;

  for (const eventType of eventTypes) {
    eventSource.addEventListener(eventType, (e: MessageEvent) => {
      console.log(`[SSE] 事件: ${eventType}, 原始数据:`, e.data);
      let data: AnalysisProgress;
      try {
        data = JSON.parse(e.data);
      } catch (parseErr) {
        console.error(`[SSE] JSON解析失败:`, e.data, parseErr);
        return;
      }
      onProgress(data);

      if (data.type === "complete" && data.result) {
        console.log(`[SSE] 分析完成, rating=${data.result.overall_rating}`);
        eventSource.close();
        resolveResult(data.result);
      } else if (data.type === "cached" && data.result) {
        console.log(`[SSE] 缓存命中, rating=${data.result.overall_rating}`);
        eventSource.close();
        resolveResult(data.result);
      } else if (data.type === "error") {
        console.error(`[SSE] 服务端错误: ${data.error}`);
        eventSource.close();
        rejectResult(new Error(data.error || "分析失败"));
      }
    });
  }

  eventSource.onopen = () => {
    console.log(`[SSE] 连接已建立: ${url}`);
  };

  eventSource.onerror = (e) => {
    console.error(`[SSE] 连接错误:`, e, `readyState=${eventSource.readyState}`);
    eventSource.close();
    rejectResult(new Error("连接断开，请重试"));
  };

  const cancel = () => {
    console.log(`[SSE] 主动取消`);
    eventSource.close();
  };

  return { promise, cancel };
}
