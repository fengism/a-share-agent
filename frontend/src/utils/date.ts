import dayjs from "dayjs";

/** 日线本地库最长覆盖 10 年，前端最多也只能回溯到该窗口。 */
export const MAX_KLINE_HISTORY_YEARS = 10;

export function oneYearAgoDate() {
  return dayjs().subtract(1, "year").format("YYYYMMDD");
}

/** 返回 N 年前的 YYYYMMDD；N 会被收敛到 [0, MAX_KLINE_HISTORY_YEARS]。 */
export function yearsAgoDate(years: number) {
  const clamped = Math.min(Math.max(Math.round(years), 0), MAX_KLINE_HISTORY_YEARS);
  return dayjs().subtract(clamped, "year").format("YYYYMMDD");
}

/** 判断两个 YYYYMMDD 之间的距离是否已接近支持上限。 */
export function isAtKlineHistoryLimit(startDate: string) {
  return Boolean(startDate) && startDate <= yearsAgoDate(MAX_KLINE_HISTORY_YEARS);
}

export function normalizeIsoDate(value: string, fallback: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return fallback;
  const parsed = dayjs(value);
  return parsed.isValid() && parsed.format("YYYY-MM-DD") === value ? value : fallback;
}
