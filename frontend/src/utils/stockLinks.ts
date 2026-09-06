export function normalizeAshareStockCode(code: string): string | null {
  const match = code.trim().match(/^(?:(?:SH|SZ|BJ))?(\d{6})(?:\.(?:SH|SZ|BJ))?$/i);
  return match?.[1] ?? null;
}

export function buildStockProfileUrl(code: string): string {
  return `/stock/${encodeURIComponent(code.trim())}`;
}

export function buildStockAnalysisUrl(code: string): string {
  return `/analysis/${encodeURIComponent(code.trim())}`;
}

export function buildWatchlistStockUrl(code: string, market?: "cn" | "hk"): string {
  const cleanCode = code.trim();
  return market === "hk"
    ? `/market?market=hk${cleanCode ? `&code=${encodeURIComponent(cleanCode)}` : ""}`
    : buildStockProfileUrl(cleanCode);
}
