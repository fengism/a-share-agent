import type { Dayjs } from "dayjs";
import type { QuantStrategyDraft } from "../../api/queries";

export interface DraftBacktestValues {
  codes: string;
  dateRange: [Dayjs, Dayjs];
  benchmark: string;
  minimumTradeCount: number;
  maximumDrawdownPct: number;
  minimumSharpeRatio?: number;
  minimumHoldoutTradeCount?: number;
  maximumHoldoutDrawdownPct?: number;
  minimumHoldoutSharpeRatio?: number;
}

export const STRATEGY_DRAFT_STATUS_META: Record<
  QuantStrategyDraft["status"],
  { color: string; label: string }
> = {
  draft: { color: "default", label: "待校验" },
  validated: { color: "blue", label: "已校验" },
  testing: { color: "processing", label: "回测中" },
  backtested: { color: "green", label: "门禁通过" },
  published: { color: "purple", label: "已发布" },
};

export function parseDraftStockCodes(value: string): string[] {
  return [...new Set(value.split(/[\s,，]+/).map((code) => code.trim()).filter(Boolean))];
}
