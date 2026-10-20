import type { DailyReviewProgress } from "../../api/sse";

export const DAILY_REVIEW_STAGES = [
  { key: "queue", title: "排队" },
  { key: "collect", title: "采集数据" },
  { key: "analyze", title: "AI 复盘" },
  { key: "persist", title: "保存" },
] as const;

export type DailyReviewStageKey = (typeof DAILY_REVIEW_STAGES)[number]["key"];

export interface DailyReviewProgressState {
  done: DailyReviewStageKey[];
  current: DailyReviewStageKey | "";
  collect: { done: number; total: number; failed: number } | null;
  elapsedMs: number;
  cached: boolean;
}

export const EMPTY_DAILY_REVIEW_PROGRESS: DailyReviewProgressState = {
  done: [],
  current: "",
  collect: null,
  elapsedMs: 0,
  cached: false,
};

export function reduceDailyReviewProgress(
  state: DailyReviewProgressState,
  event: DailyReviewProgress,
): DailyReviewProgressState {
  const stage = event.stage as DailyReviewStageKey | undefined;
  switch (event.type) {
    case "stage_started":
      return stage ? { ...state, current: stage } : state;
    case "stage_completed": {
      if (!stage) return state;
      const done = state.done.includes(stage) ? state.done : [...state.done, stage];
      const collect = stage === "collect"
        ? { done: event.sources ?? state.collect?.done ?? 0, total: event.sources ?? 0, failed: event.failed ?? 0 }
        : state.collect;
      return { ...state, done, current: "", collect };
    }
    case "source_done": {
      const failed = (state.collect?.failed ?? 0) + (event.status === "unavailable" ? 1 : 0);
      return {
        ...state,
        collect: { done: event.done ?? 0, total: event.total ?? state.collect?.total ?? 0, failed },
      };
    }
    case "stage_progress":
      return typeof event.elapsed_ms === "number" ? { ...state, elapsedMs: event.elapsed_ms } : state;
    case "cache_hit":
      return { ...state, cached: true };
    default:
      return state;
  }
}

export function buildDailyReviewStepItems(state: DailyReviewProgressState) {
  // 只有「已开始」的阶段才算 process：还没收到任何事件时不该有一步显示进行中。
  const currentIndex = state.current
    ? DAILY_REVIEW_STAGES.findIndex((stage) => stage.key === state.current)
    : -1;
  return DAILY_REVIEW_STAGES.map((stage, index) => {
    const finished = state.done.includes(stage.key);
    let description: string | undefined;
    if (stage.key === "collect" && state.collect) {
      const { done, total, failed } = state.collect;
      description = failed > 0 ? `已完成 ${done}/${total}，${failed} 个源不可用` : `已完成 ${done}/${total}`;
    } else if (stage.key === "analyze" && state.elapsedMs > 0 && !finished) {
      description = `已用 ${Math.round(state.elapsedMs / 1000)}s`;
    } else if (finished) {
      description = "已完成";
    }
    const status = finished ? "finish" : index === currentIndex ? "process" : "wait";
    return { title: stage.title, description, status } as const;
  });
}
