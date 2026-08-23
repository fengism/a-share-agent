export function normalizeAshareStockCode(code: string): string | null {
  const match = code.trim().match(/(?:^|\D)(\d{6})(?!\d)/);
  return match?.[1] ?? null;
}
