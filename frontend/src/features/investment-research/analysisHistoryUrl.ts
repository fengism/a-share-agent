import dayjs from "dayjs";
import { buildStockProfileUrl } from "../../utils/stockLinks";

export type AnalysisDateState =
  | { kind: "missing"; date: "" }
  | { kind: "invalid"; date: "" }
  | { kind: "valid"; date: string };

export function parseAnalysisDate(value: string | null | undefined): AnalysisDateState {
  if (!value) return { kind: "missing", date: "" };
  const compact = /^\d{8}$/.test(value) ? value : value.replace(/-/g, "");
  if (!/^\d{8}$/.test(compact)) return { kind: "invalid", date: "" };
  const parsed = dayjs(`${compact.slice(0, 4)}-${compact.slice(4, 6)}-${compact.slice(6, 8)}`);
  if (!parsed.isValid() || parsed.format("YYYYMMDD") !== compact) {
    return { kind: "invalid", date: "" };
  }
  return { kind: "valid", date: compact };
}

export function normalizeAnalysisDate(value: string | null | undefined): string {
  return parseAnalysisDate(value).date;
}

export function buildAnalysisHistoryUrl(
  code: string,
  date: string,
  routeBase = "/analysis",
): string {
  const normalizedDate = normalizeAnalysisDate(date);
  const normalizedBase = routeBase.endsWith("/") ? routeBase.slice(0, -1) : routeBase;
  const basePath = `${normalizedBase}/${encodeURIComponent(code)}`;
  return normalizedDate ? `${basePath}?date=${normalizedDate}` : basePath;
}

export function formatAnalysisDate(date: string): string {
  const normalizedDate = normalizeAnalysisDate(date);
  if (!normalizedDate) return date;
  return `${normalizedDate.slice(0, 4)}-${normalizedDate.slice(4, 6)}-${normalizedDate.slice(6, 8)}`;
}

export function buildStockValuationUrl(code: string, date?: string | null): string {
  const params = new URLSearchParams({ tab: "valuation" });
  const normalizedDate = normalizeAnalysisDate(date);
  if (normalizedDate) params.set("date", normalizedDate);
  return `${buildStockProfileUrl(code)}?${params.toString()}#stock-details`;
}
