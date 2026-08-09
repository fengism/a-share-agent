import type { QuantBacktestRun, QuantStrategyConfig } from "../../api/queries";

export const QUANT_RUN_STATUS_META: Record<QuantBacktestRun["status"], { label: string; color: string }> = {
  pending: { label: "等待中", color: "blue" },
  running: { label: "运行中", color: "processing" },
  succeeded: { label: "已完成", color: "green" },
  failed: { label: "失败", color: "red" },
  cancelled: { label: "已取消", color: "default" },
};

export const QUANT_STRATEGY_LABELS: Record<QuantStrategyConfig["type"], string> = {
  ma_cross: "双均线趋势",
  momentum_breakout: "动量突破",
  rsi_reversion: "RSI 均值回归",
};

export function quantUniverseLabel(run: QuantBacktestRun): string {
  return (run.request.universe.codes ?? []).join("、") || "当前持仓";
}
