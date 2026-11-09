const CSV_FORMULA_PREFIX = /^[=+\-@\t\r]/;
const NUMERIC_LIKE = /^[+-]?\d[\d,.]*(?:\s*(?:亿份|亿元|%|x))?$/i;

function needsFormulaGuard(value: string) {
  if (!CSV_FORMULA_PREFIX.test(value)) return false;
  // 负数与带单位金额是正常数据，不能为了防公式注入把负号也转义掉。
  return !NUMERIC_LIKE.test(value);
}

export function escapeCsvCell(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "number") return String(value);
  let text = String(value);
  if (needsFormulaGuard(text)) text = `'${text}`;
  if (/[",\n\r]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

export function serializeCsvRows(rows: readonly (readonly unknown[])[]): string {
  return "\uFEFF" + rows.map((row) => row.map(escapeCsvCell).join(",")).join("\r\n");
}

export function downloadCsv(filename: string, rows: readonly (readonly unknown[])[]): boolean {
  if (typeof window === "undefined" || typeof URL.createObjectURL !== "function") return false;
  const blob = new Blob([serializeCsvRows(rows)], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.setAttribute("href", url);
  link.setAttribute("download", filename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  // 立即 revoke 在部分浏览器会打断下载，延后到下一轮事件循环。
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
  return true;
}
