export function formatPercent(value?: number | null): string {
  return value == null ? "-" : `${value.toFixed(2)}%`;
}

export function formatNumber(value?: number | null): string {
  return value == null ? "-" : value.toFixed(2);
}

export function formatRatio(value?: number | null, decimals = 2): string {
  return value == null ? "-" : value.toFixed(decimals);
}

