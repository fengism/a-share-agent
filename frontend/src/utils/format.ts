import { getColors } from "../theme/store";
import type { ThemeColors } from "../theme/themes";

export function formatSignedPercent(value: number | null | undefined, digits = 2) {
  if (value == null) return "-";
  return `${value > 0 ? "+" : ""}${value.toFixed(digits)}%`;
}

export function formatRatioPercent(value: number | null | undefined, digits = 1) {
  if (value == null) return "-";
  return `${(value * 100).toFixed(digits)}%`;
}

export function formatHotValue(value: number | null | undefined) {
  if (value == null) return "-";
  if (value >= 10000) return `${(value / 10000).toFixed(1)}万`;
  return value.toFixed(0);
}

export function formatWanAmount(value: number | null | undefined) {
  if (value == null) return "-";
  if (Math.abs(value) >= 10000) return `${(value / 10000).toFixed(2)}亿`;
  return `${value.toFixed(0)}万`;
}

export function formatNumber(value: number | null | undefined, digits = 2) {
  if (value == null) return "-";
  return value.toFixed(digits);
}

export function changeColor(value: number | null | undefined, c?: ThemeColors) {
  const colors = c ?? getColors();
  if (value == null) return colors.textSecondary;
  return value > 0 ? colors.up : value < 0 ? colors.down : colors.textSecondary;
}

export function formatMarketCap(value: number | null | undefined) {
  if (value == null) return "-";
  if (Math.abs(value) >= 1e12) return `${(value / 1e12).toFixed(2)}万亿`;
  if (Math.abs(value) >= 1e8) return `${(value / 1e8).toFixed(2)}亿`;
  return value.toFixed(0);
}

export function formatAmount(value: number | null | undefined) {
  if (value == null) return "-";
  if (Math.abs(value) >= 1e8) return `${(value / 1e8).toFixed(1)}亿`;
  if (Math.abs(value) >= 1e4) return `${(value / 1e4).toFixed(1)}万`;
  return value.toFixed(0);
}

export function formatAmountWanYi(value: number | null | undefined) {
  if (value == null) return "-";
  if (Math.abs(value) >= 1e8) return `${(value / 1e8).toFixed(2)}亿`;
  return `${(value / 1e4).toFixed(2)}万`;
}
