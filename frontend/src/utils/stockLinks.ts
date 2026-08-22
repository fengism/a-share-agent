const EASTMONEY_STOCK_DATA_BASE_URL = "https://data.eastmoney.com/stockdata";

export function normalizeAshareStockCode(code: string): string | null {
  const match = code.trim().match(/(?:^|\D)(\d{6})(?!\d)/);
  return match?.[1] ?? null;
}

export function getEastmoneyStockUrl(code: string): string | null {
  const normalizedCode = normalizeAshareStockCode(code);
  return normalizedCode
    ? `${EASTMONEY_STOCK_DATA_BASE_URL}/${normalizedCode}.html`
    : null;
}
