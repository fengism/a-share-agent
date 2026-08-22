import type { AnalysisResult } from "../../types/stock";

export interface ConditionalAction {
  label: "关注" | "观察" | "谨慎";
  detail: string;
  tone: "positive" | "neutral" | "negative";
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
