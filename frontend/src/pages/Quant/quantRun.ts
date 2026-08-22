import type { QuantBacktestRun, QuantStrategyConfig } from "../../api/queries";
import type { SemanticTagColor } from "../../theme/hooks";
import { strategyOptions } from "./quantForm";

export const QUANT_RUN_STATUS_META: Record<QuantBacktestRun["status"], { label: string; color: SemanticTagColor }> = {
  pending: { label: "等待中", color: "info" },
  running: { label: "运行中", color: "primary" },
  succeeded: { label: "已完成", color: "down" },
  failed: { label: "失败", color: "up" },
  cancelled: { label: "已取消", color: "info" },
};

export function quantStrategyLabel(strategy: QuantStrategyConfig): string {
  return strategy.name
    ?? strategyOptions().find((option) => option.value === strategy.type)?.label
    ?? strategy.type;
}

export function quantUniverseLabel(run: QuantBacktestRun): string {
  return (run.request.universe.codes ?? []).join("、") || "当前持仓";
}


export function quantStrategyIdentity(strategy: QuantStrategyConfig): string {
  const version = strategy.version ? `@${strategy.version}` : "";
  return `${quantStrategyLabel(strategy)} · ${strategy.type}${version}`;
}

export function quantStrategyParameterSummary(strategy: QuantStrategyConfig): string {
  const entries = Object.entries(strategy.parameters ?? {});
  if (entries.length === 0) return "默认参数";
  return entries.map(([key, value]) => `${key}=${String(value)}`).join(" · ");
}
