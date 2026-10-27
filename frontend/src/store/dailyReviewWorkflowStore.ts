import { create } from "zustand";
import type { DailyReviewProgress, WorkflowStream } from "../api/sse";
import type { DailyReviewResult } from "../types/dailyReview";
import {
  EMPTY_DAILY_REVIEW_PROGRESS,
  reduceDailyReviewProgress,
  type DailyReviewProgressState,
} from "../pages/DailyReview/progress";
import { registerUserScopeHandler } from "./userScope";

export interface DailyReviewWorkflowState {
  runId: number;
  jobId: string;
  date: string;
  isGenerating: boolean;
  isCancelling: boolean;
  message: string;
  progress: DailyReviewProgressState;
  stream: WorkflowStream<DailyReviewResult> | null;
  begin: (date: string) => number;
  patch: (runId: number, patch: Partial<DailyReviewWorkflowState>) => void;
  applyProgress: (runId: number, event: DailyReviewProgress) => void;
  setStream: (runId: number, stream: WorkflowStream<DailyReviewResult>) => void;
  stopRun: (runId: number, outcome: "cancelled" | "detached") => void;
  cancelActiveRun: () => Promise<"cancelled" | "detached" | "completed" | null>;
  clear: () => void;
}

const initialState = () => ({
  runId: 0,
  jobId: "",
  date: "",
  isGenerating: false,
  isCancelling: false,
  message: "",
  progress: EMPTY_DAILY_REVIEW_PROGRESS,
  stream: null as WorkflowStream<DailyReviewResult> | null,
});

export const useDailyReviewWorkflowStore = create<DailyReviewWorkflowState>((set, get) => ({
  ...initialState(),
  begin: (date) => {
    const runId = get().runId + 1;
    set({
      ...initialState(),
      runId,
      date,
      isGenerating: true,
      message: "正在提交每日复盘任务",
      progress: EMPTY_DAILY_REVIEW_PROGRESS,
    });
    return runId;
  },
  patch: (runId, patch) => set((state) => (state.runId === runId ? patch : state)),
  applyProgress: (runId, event) => set((state) => {
    if (state.runId !== runId || !state.isGenerating) return state;
    return {
      message: event.message || state.message,
      progress: reduceDailyReviewProgress(state.progress, event),
    };
  }),
  setStream: (runId, stream) => set((state) => (state.runId === runId ? { stream } : state)),
  stopRun: (runId, outcome) => set((state) => {
    if (state.runId !== runId || !state.isGenerating) return state;
    const message = outcome === "cancelled" ? "每日复盘任务已取消" : "已停止等待，后台共享任务仍在运行";
    return { isGenerating: false, isCancelling: false, message, stream: null };
  }),
  cancelActiveRun: async () => {
    const current = get();
    if (!current.isGenerating || !current.stream || current.isCancelling) return null;
    const runId = current.runId;
    set({ isCancelling: true, message: "正在取消每日复盘任务" });
    try {
      const result = await current.stream.cancel();
      if (result === "completed") {
        set((latest) => (latest.runId === runId && latest.isGenerating
          ? { message: "任务已完成，正在接收复盘结果" }
          : latest));
      } else {
        get().stopRun(runId, result);
      }
      return result;
    } catch (error) {
      set((latest) => (latest.runId === runId && latest.isGenerating
        ? { isCancelling: false, message: `取消失败，任务继续运行：${error instanceof Error ? error.message : "请重试"}` }
        : latest));
      throw error;
    }
  },
  clear: () => {
    get().stream?.detach();
    set({ ...initialState(), runId: get().runId + 1 });
  },
}));

registerUserScopeHandler(() => {
  useDailyReviewWorkflowStore.getState().clear();
});
