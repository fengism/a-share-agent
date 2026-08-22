export function formatPercent(value?: number | null): string {
  return value == null ? "-" : `${value.toFixed(2)}%`;
}

export function formatNumber(value?: number | null): string {
  return value == null ? "-" : value.toFixed(2);
}
