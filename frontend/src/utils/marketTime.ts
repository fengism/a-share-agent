/**
 * A 股终端的时间显示收口。
 *
 * 后端把行情、复盘、任务等时间戳统一按**北京时间墙上时钟**落库（`market_now()`
 * 返回 naive 值，序列化后没有时区后缀）。浏览器 `new Date("2026-10-22T20:57:00")`
 * 会把它当成**浏览器本地时间**解析，于是海外/出差用户在非 UTC+8 时区看到的
 * "行情时间"会整体偏移（UTC 环境差 8 小时；纯日期 "2026-10-22" 按 UTC 零点解析，
 * 在西半球还会差一天）。
 *
 * 因此凡是把后端时间串喂给 `Date` / `dayjs` 的地方都走这里：
 * 无时区后缀按 +08:00 解释，渲染统一锁 Asia/Shanghai。
 *
 * 例外：分时图（`charts/IntradayChart.tsx`、`charts/intradayTimeRange.ts`）内部
 * 用 `getUTC*` 把时间戳当作"市场墙上时钟"直接上轴，自身前后一致，不要改。
 */

export const MARKET_TIME_ZONE = "Asia/Shanghai";

const MARKET_UTC_OFFSET = "+08:00";

/** 已带时区信息（Z 或 ±HH:MM / ±HHMM）的串按绝对时刻处理，不再改写。 */
const HAS_TIMEZONE = /(?:[zZ]|[+-]\d{2}:?\d{2})$/;

const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

/** "2026-10-22 20:57" / "2026-10-22T20:57:00" / "2026-10-22T20:57:00.123" */
const LOCAL_WALL_CLOCK = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,3})?)?$/;

export type MarketTimeInput = string | number | Date | null | undefined;

/**
 * 把后端时间解析成绝对时刻。
 *
 * - 无时区后缀的日期/时间串：按 +08:00 解释
 * - 纯日期串：按北京时间当天 00:00 解释
 * - 带时区后缀的串、`Date`：原样使用
 * - 数字：秒级/毫秒级 epoch 自适应
 *
 * 无法解析时返回 `null`，调用方自行给兜底文案。
 */
export function parseMarketTime(value: MarketTimeInput): Date | null {
  if (value === null || value === undefined) return null;
  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value;
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return null;
    // 后端习惯用秒级 epoch（10 位），也兼容毫秒级（13 位）
    const ms = Math.abs(value) < 1e11 ? value * 1000 : value;
    const date = new Date(ms);
    return Number.isNaN(date.getTime()) ? null : date;
  }
  const text = value.trim();
  if (!text) return null;
  if (DATE_ONLY.test(text)) {
    const date = new Date(`${text}T00:00:00${MARKET_UTC_OFFSET}`);
    return Number.isNaN(date.getTime()) ? null : date;
  }
  if (!HAS_TIMEZONE.test(text) && LOCAL_WALL_CLOCK.test(text)) {
    const date = new Date(`${text.replace(" ", "T")}${MARKET_UTC_OFFSET}`);
    return Number.isNaN(date.getTime()) ? null : date;
  }
  const date = new Date(text);
  return Number.isNaN(date.getTime()) ? null : date;
}

const formatterCache = new Map<string, Intl.DateTimeFormat>();

function marketFormatter(options: Intl.DateTimeFormatOptions): Intl.DateTimeFormat {
  const key = JSON.stringify(options);
  const cached = formatterCache.get(key);
  if (cached) return cached;
  const formatter = new Intl.DateTimeFormat("zh-CN", { timeZone: MARKET_TIME_ZONE, ...options });
  formatterCache.set(key, formatter);
  return formatter;
}

/** 按北京时间渲染，格式由 `options` 决定；解析失败返回 `fallback`。 */
export function formatMarketTime(
  value: MarketTimeInput,
  options: Intl.DateTimeFormatOptions = {},
  fallback = "-",
): string {
  const date = parseMarketTime(value);
  if (!date) return fallback;
  try {
    return marketFormatter({ hour12: false, hourCycle: "h23", ...options }).format(date);
  } catch {
    return fallback;
  }
}

const DATE_TIME_OPTIONS: Intl.DateTimeFormatOptions = {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
  hourCycle: "h23",
};

/** "2026/10/22 20:57:00" */
export function formatMarketDateTime(value: MarketTimeInput, fallback = "-"): string {
  return formatMarketTime(value, DATE_TIME_OPTIONS, fallback);
}

/** "10/22 20:57" */
export function formatMarketMonthDayClock(value: MarketTimeInput, fallback = "-"): string {
  return formatMarketTime(
    value,
    { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" },
    fallback,
  );
}

/** "20:57" */
export function formatMarketClock(value: MarketTimeInput, fallback = "-"): string {
  return formatMarketTime(
    value,
    { hour: "2-digit", minute: "2-digit", hourCycle: "h23" },
    fallback,
  );
}

const PATTERN_PARTS: Intl.DateTimeFormatOptions = {
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hourCycle: "h23",
};

const PATTERN_TOKENS: Record<string, string> = {
  YYYY: "year",
  MM: "month",
  DD: "day",
  HH: "hour",
  mm: "minute",
  ss: "second",
};

/**
 * 按 `YYYY` / `MM` / `DD` / `HH` / `mm` / `ss` 模板渲染北京时间，
 * 用于保留调用点原有的破折号风格（`2026-10-22 20:57`）。
 */
export function formatMarketPattern(
  value: MarketTimeInput,
  pattern: string,
  fallback = "-",
): string {
  const date = parseMarketTime(value);
  if (!date) return fallback;
  const parts: Record<string, string> = {};
  for (const part of marketFormatter(PATTERN_PARTS).formatToParts(date)) {
    if (part.type !== "literal") parts[part.type] = part.value;
  }
  return pattern.replace(/YYYY|MM|DD|HH|mm|ss/g, (token) => parts[PATTERN_TOKENS[token]] ?? token);
}

/** 北京时间的「今天」，`YYYY-MM-DD`（导出文件名、默认查询日等场景）。 */
export function marketDateStamp(value: MarketTimeInput = Date.now()): string {
  return formatMarketPattern(value, "YYYY-MM-DD", "");
}

/** "2026/10/22" */
export function formatMarketDate(value: MarketTimeInput, fallback = "-"): string {
  return formatMarketTime(
    value,
    { year: "numeric", month: "2-digit", day: "2-digit" },
    fallback,
  );
}
