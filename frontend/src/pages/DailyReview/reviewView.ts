/**
 * 每日复盘的视图模型。
 *
 * 页面渲染、Markdown 导出、研报长图都从这里取数据，避免三处各写一遍
 * 取值/格式规则而逐渐漂移。纯函数，无 React 依赖，便于单测。
 */

import type { DailyReviewResult } from "../../types/dailyReview";

/**
 * 复盘的视图输入即接口返回结构；额外允许测试/工具传入的精简对象
 * （用 `Partial` 放宽必填项，其余字段按需可选读取）。
 */
export type DailyReviewPayload = Omit<Partial<DailyReviewResult>, "data_snapshot"> & {
  date: string;
  title: string;
  market_summary: string;
  data_snapshot: DailyReviewResult["data_snapshot"];
};

/** 复盘关键指标（Hero 区三数 + 情绪/质量） */
export interface ReviewHeadline {
  limitUpCount: number | null;
  breakRate: number | null;
  indexChangePct: number | null;
  indexName: string | null;
  stage: string | null;
  quality: "complete" | "degraded";
  generation: "ai" | "fallback";
  /** 昨日自检命中情况，用于 Hero 右侧小卡 */
  checkHit: number | null;
  checkTotal: number | null;
}

function num(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

/**
 * 比例型字段（如炸板率）后端可能给 0.18 或 18，统一成百分数。
 *
 * 注意：指数涨跌幅这类"本身就以百分数表示"的字段不要走这里，
 * 否则 0.85%（正常单日波动）会被误放大成 85%。
 */
function ratioToPercent(value: unknown): number | null {
  const raw = num(value);
  if (raw === null) return null;
  return Math.abs(raw) <= 1 ? raw * 100 : raw;
}

export function formatSignedPct(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
}

/** 首屏「今日结论」的一句话摘要 */
export function buildMoodSummary(review: DailyReviewPayload): string {
  const indices = review.data_snapshot.indices ?? [];
  const rising = indices.filter((item) => Number(item.change_pct ?? 0) > 0).length;
  const falling = indices.filter((item) => Number(item.change_pct ?? 0) < 0).length;
  const strongest = review.data_snapshot.top_sectors?.[0];
  const weakest = review.data_snapshot.bottom_sectors?.[0];
  const indexMood = rising > falling ? "指数偏强" : rising < falling ? "指数偏弱" : "指数分化";
  const sectorMood = strongest && weakest
    ? `强势板块为${String(strongest.name)}，弱势板块为${String(weakest.name)}`
    : "板块强弱暂不明显";
  return `${indexMood}，${sectorMood}`;
}

/** 抽取 Hero 区需要的核心指标 */
export function buildReviewHeadline(review: DailyReviewPayload): ReviewHeadline {
  const stats = review.data_snapshot.market_statistics ?? {};
  const limitUp =
    num(stats.limit_up_count) ?? num(stats.limit_up) ?? num(stats.zt_count) ?? null;
  const breakRate =
    ratioToPercent(stats.break_rate) ?? ratioToPercent(stats.limit_up_break_rate) ?? null;

  const primaryIndex = (review.data_snapshot.indices ?? [])[0];
  // 指数涨跌幅后端已是百分数（0.85 表示 +0.85%），直接取值
  const indexChangePct = primaryIndex ? num(primaryIndex.change_pct) : null;

  const check = review.previous_review_check;
  const checkTotal = check?.checked_count ?? null;
  const checkHit = check?.hit_count ?? null;

  return {
    limitUpCount: limitUp,
    breakRate,
    indexChangePct,
    indexName: primaryIndex ? String(primaryIndex.name ?? primaryIndex.code ?? "") : null,
    stage: review.sentiment_cycle?.stage ?? null,
    quality: review.quality_status === "degraded" ? "degraded" : "complete",
    generation: review.generation_status === "fallback" ? "fallback" : "ai",
    checkHit,
    checkTotal,
  };
}

export interface ReviewSectionDescriptor {
  id: string;
  title: string;
  /** 章节目录上的摘要计数 */
  count?: number;
  /** 是否有内容（无内容则不渲染） */
  available: boolean;
}

/** 分区清单：目录、折叠卡与导出顺序的唯一来源 */
export function buildReviewSections(review: DailyReviewPayload): ReviewSectionDescriptor[] {
  const check = review.previous_review_check;
  const trendPoints = review.cycle_trend?.points ?? [];
  const sections: ReviewSectionDescriptor[] = [
    {
      id: "review-charts",
      title: "市场图谱",
      available: true,
    },
    {
      id: "review-policy",
      title: "政策与事件传导",
      count: (review.event_impacts?.length ?? 0) + (review.news_policy_review?.bullets.length ?? 0),
      available: Boolean(review.news_policy_review || review.event_impacts?.length),
    },
    {
      id: "review-sentiment",
      title: "情绪周期定位",
      count: review.sentiment_cycle?.evidence?.length ?? 0,
      available: Boolean(review.sentiment_cycle),
    },
    {
      id: "review-scenarios",
      title: "明日三情景预案",
      count: review.scenario_plans?.length ?? 0,
      available: Boolean(review.scenario_plans?.length),
    },
    {
      id: "review-watchlist",
      title: "次日观察锚点",
      count: review.next_day_watchlist?.length ?? 0,
      available: Boolean(review.next_day_watchlist?.length),
    },
    {
      id: "review-key-levels",
      title: "关键点位与量能阈值",
      count: review.key_levels?.length ?? 0,
      available: Boolean(review.key_levels?.length),
    },
    {
      id: "review-self-check",
      title: "昨日复盘自检",
      count: check?.checked_count ?? 0,
      available: Boolean(check),
    },
    {
      id: "review-cycle-trend",
      title: "情绪周期历史趋势",
      count: trendPoints.length,
      available: trendPoints.length > 0,
    },
    {
      id: "review-data-status",
      title: "复盘数据状态",
      available: Boolean(review.data_snapshot.source_status),
    },
    {
      id: "review-report",
      title: review.llm_review ? "深度复盘报告" : "机会、风险与策略",
      available: true,
    },
  ];
  return sections.filter((section) => section.available);
}

/** 自检命中率（0~1），无可核验样本时返回 null */
export function buildCheckAccuracy(review: DailyReviewPayload): number | null {
  const check = review.previous_review_check;
  const total = check?.checked_count ?? 0;
  const hit = check?.hit_count ?? 0;
  if (!total) return null;
  return hit / total;
}

/** 情绪周期阶段 → 语义色标记，供时间轴/徽标共用 */
export function stageTone(stage?: string | null): "up" | "down" | "warning" | "neutral" {
  if (!stage) return "neutral";
  if (stage.includes("高潮") || stage.includes("一致")) return "up";
  if (stage.includes("冰点") || stage.includes("退潮")) return "down";
  if (stage.includes("分歧") || stage.includes("修复")) return "warning";
  return "neutral";
}
