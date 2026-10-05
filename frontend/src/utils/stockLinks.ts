export type MarketType = "cn" | "hk";

export interface ParsedStockCode {
  code: string;
  market: MarketType;
}

export function parseStockCode(raw: string): ParsedStockCode | null {
  const trimmed = (raw || "").trim();
  if (!trimmed) return null;
  // 1. A-share: 6 digits (optional SH/SZ/BJ prefix or suffix)
  const aMatch = trimmed.match(/^(?:(?:SH|SZ|BJ))?(\d{6})(?:\.(?:SH|SZ|BJ))?$/i);
  if (aMatch?.[1]) {
    return { code: aMatch[1], market: "cn" };
  }
  // 2. HK stock: 1-5 digits (optional HK prefix or .HK suffix)
  const hkMatch = trimmed.match(/^(?:HK)?(\d{1,5})(?:\.HK)?$/i);
  if (hkMatch?.[1]) {
    return { code: hkMatch[1].padStart(5, "0"), market: "hk" };
  }
  return null;
}

export function normalizeAshareStockCode(code: string): string | null {
  const match = (code || "").trim().match(/^(?:(?:SH|SZ|BJ))?(\d{6})(?:\.(?:SH|SZ|BJ))?$/i);
  return match?.[1] ?? null;
}

export function normalizeHkStockCode(code: string): string | null {
  const match = (code || "").trim().match(/^(?:HK)?(\d{1,5})(?:\.HK)?$/i);
  return match?.[1] ? match[1].padStart(5, "0") : null;
}

/** 港股代码为 1-5 位，与 6 位 A 股天然互斥，因此无需额外市场参数即可判定。 */
export function isHkStockCode(code: string): boolean {
  return normalizeHkStockCode(code) !== null;
}

export function buildStockProfileUrl(code: string): string {
  return `/stock/${encodeURIComponent(code.trim())}`;
}

export function buildStockAnalysisUrl(code: string): string {
  return `/analysis/${encodeURIComponent(code.trim())}`;
}

export function buildWatchlistStockUrl(code: string, market?: "cn" | "hk"): string {
  const cleanCode = (code || "").trim();
  if (market === "hk") {
    if (!cleanCode) return "/market?market=hk";
    const normalized = normalizeHkStockCode(cleanCode) || cleanCode;
    return buildStockProfileUrl(normalized);
  }
  return buildStockProfileUrl(cleanCode);
}
