export function normalizeAnalysisDate(value: string | null): string {
  return value && /^\d{8}$/.test(value) ? value : "";
}

export function buildAnalysisHistoryUrl(code: string, date: string): string {
  const normalizedDate = normalizeAnalysisDate(date);
  const basePath = `/analysis/${encodeURIComponent(code)}`;
  return normalizedDate ? `${basePath}?date=${normalizedDate}` : basePath;
}

export function formatAnalysisDate(date: string): string {
  const normalizedDate = normalizeAnalysisDate(date);
  if (!normalizedDate) return date;
  return `${normalizedDate.slice(0, 4)}-${normalizedDate.slice(4, 6)}-${normalizedDate.slice(6, 8)}`;
}
