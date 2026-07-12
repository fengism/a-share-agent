import type { BusinessDay } from "lightweight-charts";

/**
 * Parse a date string into a BusinessDay object for lightweight-charts.
 * Accepts YYYYMMDD or YYYY-MM-DD / YYYY/MM/DD formats.
 */
export function toBusinessDay(value: string): BusinessDay | null {
  const text = String(value || "").trim();
  if (!text) return null;
  const normalized = /^\d{8}$/.test(text)
    ? `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6, 8)}`
    : /^\d{4}[/-]\d{2}[/-]\d{2}/.test(text)
      ? text.slice(0, 10).replace(/\//g, "-")
      : null;
  if (!normalized) return null;
  const [year, month, day] = normalized.split("-").map(Number);
  return year && month && day ? { year, month, day } : null;
}

/**
 * Convert a hex color string to rgba format.
 */
export function hexToRgba(hex: string, alpha: number): string {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}
