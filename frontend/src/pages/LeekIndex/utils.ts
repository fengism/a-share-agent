export function formatAmount(val: number): string {
  const abs = Math.abs(val);
  if (abs >= 1e8) {
    return `${(val / 1e8).toFixed(1)} 亿`;
  }
  if (abs >= 1e4) {
    return `${(val / 1e4).toFixed(0)} 万`;
  }
  return `${val.toFixed(0)} 元`;
}

export function formatSignedAmount(val: number): string {
  const abs = Math.abs(val);
  const sign = val > 0 ? "+" : val < 0 ? "-" : "";
  if (abs >= 1e8) {
    return `${sign}${(abs / 1e8).toFixed(1)} 亿`;
  }
  if (abs >= 1e4) {
    return `${sign}${(abs / 1e4).toFixed(0)} 万`;
  }
  return `${sign}${abs.toFixed(0)} 元`;
}
