export function deriveTrajectory(
  signalTypes: string[] = [],
  strategies: string[] = [],
): { from: string; to: string } {
  const signals = new Set(signalTypes);
  const strats = strategies.join(" ");

  if (signals.has("breakout") || strats.includes("突破")) {
    return { from: "箱体蓄势", to: "顺势突破" };
  }
  if (signals.has("pullback") || strats.includes("回踩")) {
    return { from: "缩量回探", to: "支撑企稳" };
  }
  if (signals.has("reversal") || strats.includes("底部") || strats.includes("超跌")) {
    return { from: "超跌探底", to: "底部企稳" };
  }
  if (signals.has("trend") || strats.includes("趋势")) {
    return { from: "均线多头", to: "主升共振" };
  }
  if (signals.has("range") || strats.includes("箱体")) {
    return { from: "区间震荡", to: "临界蓄势" };
  }
  return { from: "形态观察", to: "信号触发" };
}
