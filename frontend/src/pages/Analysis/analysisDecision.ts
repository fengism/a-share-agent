import type { AnalysisResult } from "../../types/stock";

export interface ConditionalAction {
  label: "关注" | "观察" | "谨慎";
  detail: string;
  tone: "positive" | "neutral" | "negative";
}

export type KeyLevelStatus = "within_range" | "below_support" | "above_resistance" | "unavailable";

export interface KeyLevelInsight {
  status: KeyLevelStatus;
  label: "区间运行" | "跌破支撑" | "突破压力" | "数据待补充";
  message: string;
  supportDistancePercent: number | null;
  resistanceDistancePercent: number | null;
}

function isValidPrice(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value) && value > 0;
}

export function getKeyLevelInsight(
  current: number | null | undefined,
  support: number | null | undefined,
  resistance: number | null | undefined,
): KeyLevelInsight {
  if (!isValidPrice(current) || !isValidPrice(support) || !isValidPrice(resistance) || support >= resistance) {
    return {
      status: "unavailable",
      label: "数据待补充",
      message: "关键点位数据不足，暂无法判断当前价格位置。",
      supportDistancePercent: null,
      resistanceDistancePercent: null,
    };
  }

  const distances = {
    supportDistancePercent: ((current - support) / support) * 100,
    resistanceDistancePercent: ((current - resistance) / resistance) * 100,
  };

  if (current < support) {
    return {
      status: "below_support",
      label: "跌破支撑",
      message: "当前价已跌破支撑位，建议重新评估趋势有效性。",
      ...distances,
    };
  }

  if (current > resistance) {
    return {
      status: "above_resistance",
      label: "突破压力",
      message: "当前价已突破压力位，关注量价能否持续确认。",
      ...distances,
    };
  }

  return {
    status: "within_range",
    label: "区间运行",
    message: "当前价位于支撑—压力区间内，后续关注边界附近的量价变化。",
    ...distances,
  };
}

export function getConditionalAction(signal: string): ConditionalAction {
  if (signal === "buy" || signal === "strong_buy") {
    return { label: "关注", detail: "等待关键支撑确认后再评估", tone: "positive" };
  }
  if (signal === "sell" || signal === "strong_sell") {
    return { label: "谨慎", detail: "优先等待风险信号修复", tone: "negative" };
  }
  return { label: "观察", detail: "趋势与风险收益比尚未形成一致优势", tone: "neutral" };
}

export function getAnalysisFollowUps(result: AnalysisResult): string[] {
  const name = result.stock_name || result.stock_code;
  return [
    `为什么对${name}给出“${getConditionalAction(result.signal).label}”判断？`,
    `${name}当前结论的失效条件是什么？`,
    `${name}最近的资金流发生了什么变化？`,
    `将${name}与同行业龙头进行对比`,
    `${name}如果跌破支撑位，应重点观察什么？`,
  ];
}
