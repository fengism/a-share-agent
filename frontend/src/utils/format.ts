import { getColors } from "../theme/store";

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

export function changeColor(value: number | null | undefined) {
  if (value == null) return getColors().textSecondary;
  return value > 0 ? getColors().up : value < 0 ? getColors().down : getColors().textSecondary;
}
