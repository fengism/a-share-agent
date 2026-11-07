import { formatNumberWithSeparators } from "../../../utils/format";

export function formatShares(value: number | null | undefined) {
  return value == null ? "-" : `${formatNumberWithSeparators(value)} 亿份`;
}

export function formatSigned(value: number | null | undefined, unit = "亿份") {
  if (value == null || !Number.isFinite(value)) return "-";
  return `${value > 0 ? "+" : ""}${formatNumberWithSeparators(value)} ${unit}`;
}

export function valueColor(value: number | null | undefined, up: string, down: string, neutral: string) {
  if (value == null || value === 0) return neutral;
  return value > 0 ? up : down;
}
