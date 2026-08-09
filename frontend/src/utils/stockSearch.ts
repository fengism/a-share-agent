import type { StockSearchItem } from "../types/stock";

export function normalizeStockSearchInput(value: string): string {
  return value.trim();
}

export function getCurrentStockSearchResults<T>(
  normalizedInput: string,
  resultQuery: string,
  results: T[],
): T[] {
  return normalizedInput === normalizeStockSearchInput(resultQuery) ? results : [];
}

export function excludeStockSearchResults<T extends Pick<StockSearchItem, "code">>(
  results: T[],
  excludedCodes: readonly string[],
): T[] {
  if (excludedCodes.length === 0) return results;
  const excluded = new Set(excludedCodes);
  return results.filter((result) => !excluded.has(result.code));
}

export function resolveStockSearchCode(
  input: string,
  resultQuery: string,
  results: Pick<StockSearchItem, "code">[],
): string | null {
  const normalizedInput = normalizeStockSearchInput(input);
  if (/^\d{6}$/.test(normalizedInput)) return normalizedInput;
  if (!normalizedInput || normalizedInput !== normalizeStockSearchInput(resultQuery)) return null;
  return results[0]?.code ?? null;
}
