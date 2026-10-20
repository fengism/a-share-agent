import { describe, expect, it } from "vitest";
import {
  DAILY_REVIEW_CACHED_DESCRIPTION,
  DAILY_REVIEW_FALLBACK_DESCRIPTION,
  EMPTY_DAILY_REVIEW_PROGRESS,
  buildDailyReviewStepItems,
  reduceDailyReviewProgress,
  type DailyReviewProgressState,
} from "./progress";
import type { DailyReviewProgress } from "../../api/sse";

function apply(
  events: DailyReviewProgress[],
  initial: DailyReviewProgressState = EMPTY_DAILY_REVIEW_PROGRESS,
): DailyReviewProgressState {
  return events.reduce(reduceDailyReviewProgress, initial);
}

describe("每日复盘进度归约", () => {
  it("stage_started 只移动当前阶段", () => {
    const state = apply([{ type: "stage_started", stage: "collect", message: "采集" }]);
    expect(state.current).toBe("collect");
    expect(state.done).toEqual([]);
  });

  it("stage_completed 记入已完成并清空当前", () => {
    const state = apply([
      { type: "stage_started", stage: "queue" },
      { type: "stage_completed", stage: "queue" },
    ]);
    expect(state.done).toEqual(["queue"]);
    expect(state.current).toBe("");
  });

  it("同一阶段重复完成不会重复记录", () => {
    const state = apply([
      { type: "stage_completed", stage: "collect" },
      { type: "stage_completed", stage: "collect" },
    ]);
    expect(state.done).toEqual(["collect"]);
  });

  it("采集阶段逐源计数，并把不可用源累加", () => {
    const state = apply([
      { type: "source_done", source: "indices", status: "complete", done: 1, total: 13 },
      { type: "source_done", source: "dragon_tiger", status: "unavailable", done: 2, total: 13 },
      { type: "source_done", source: "news", status: "complete", done: 3, total: 13 },
    ]);
    expect(state.collect).toEqual({ done: 3, total: 13, failed: 1 });
  });

  it("采集完成时用后端汇总的源数量与失败数", () => {
    const state = apply([
      { type: "source_done", status: "complete", done: 1, total: 13 },
      { type: "stage_completed", stage: "collect", sources: 13, failed: 2 },
    ]);
    expect(state.collect).toEqual({ done: 13, total: 13, failed: 2 });
  });

  it("心跳只更新已用时长", () => {
    const state = apply([{ type: "stage_progress", stage: "analyze", elapsed_ms: 32000 }]);
    expect(state.elapsedMs).toBe(32000);
  });

  it("缓存命中被标记", () => {
    expect(apply([{ type: "cache_hit" }]).cached).toBe(true);
  });

  it("兜底输出被记为降级", () => {
    const state = apply([
      { type: "stage_completed", stage: "analyze", generation_status: "fallback" },
    ]);
    expect(state.degraded).not.toBe("");
    expect(state.done).toEqual(["analyze"]);
  });

  it("正常模型输出不会标记降级", () => {
    const state = apply([
      { type: "stage_completed", stage: "analyze", generation_status: "llm" },
    ]);
    expect(state.degraded).toBe("");
  });

  it("未知事件不改变状态", () => {
    const initial = apply([{ type: "stage_started", stage: "collect" }]);
    expect(apply([{ type: "complete" }], initial)).toEqual(initial);
  });
});

describe("每日复盘步骤渲染", () => {
  it("四个阶段都渲染，未开始的是 wait", () => {
    const items = buildDailyReviewStepItems(EMPTY_DAILY_REVIEW_PROGRESS);
    expect(items.map((item) => item.title)).toEqual(["排队", "采集数据", "AI 复盘", "保存"]);
    expect(items.every((item) => item.status === "wait")).toBe(true);
  });

  it("已完成阶段显示 已完成，当前阶段显示 process", () => {
    const state = apply([
      { type: "stage_completed", stage: "queue" },
      { type: "stage_started", stage: "collect" },
    ]);
    const items = buildDailyReviewStepItems(state);
    expect(items[0].status).toBe("finish");
    expect(items[1].status).toBe("process");
    expect(items[2].status).toBe("wait");
  });

  it("采集阶段显示进度与不可用源数量", () => {
    const state = apply([
      { type: "source_done", status: "complete", done: 4, total: 13 },
      { type: "source_done", status: "unavailable", done: 5, total: 13 },
    ]);
    const collect = buildDailyReviewStepItems(state)[1];
    expect(collect.description).toBe("已完成 5/13，1 个源不可用");
  });

  it("分析阶段显示已用秒数", () => {
    const state = apply([
      { type: "stage_started", stage: "analyze" },
      { type: "stage_progress", elapsed_ms: 32000 },
    ]);
    expect(buildDailyReviewStepItems(state)[2].description).toBe("已用 32s");
  });

  it("缓存命中时排队步骤显示复用而不是等待", () => {
    const items = buildDailyReviewStepItems(apply([{ type: "cache_hit" }]));
    expect(items[0].description).toBe(DAILY_REVIEW_CACHED_DESCRIPTION);
  });

  it("兜底输出在 AI 复盘步骤上可见", () => {
    const state = apply([
      { type: "stage_started", stage: "analyze" },
      { type: "stage_completed", stage: "analyze", generation_status: "fallback" },
    ]);
    const analyze = buildDailyReviewStepItems(state)[2];
    expect(analyze.description).toBe(DAILY_REVIEW_FALLBACK_DESCRIPTION);
    expect(analyze.status).toBe("finish");
  });
});
