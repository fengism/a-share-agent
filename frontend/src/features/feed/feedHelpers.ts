import dayjs from "dayjs";
import type { FeedNewsItem } from "../../types/stock";
import { formatMarketPattern, parseMarketTime } from "../../utils/marketTime";
import type { ThemeColors } from "../../theme/themes";

/** Shared presentation helpers for market news and social feeds. */

/* ── 配色常量 ── */

// 7×24 快讯高亮与"30 分钟内"时间戳颜色统一走主题 warning token，深浅色一致。
// 媒体源品牌色（华尔街见闻/36氪/雪球…）保持各自品牌识别，不做 token 化。

function getSourceColors(c: ThemeColors): Record<string, string> {
  return {
    "东方财富": c.primary,
    "财联社": c.up,
    "百度": c.primary,
    "华尔街见闻": "#a78bfa",
    "36氪": "#38bdf8",
    "雪球": "#f87171",
    "界面新闻": "#34d399",
    "经济观察报": "#818cf8",
    "Twitter": c.primary,
    "联合早报": "#c084fc",
    "cnnews": "#4ade80",
    "其他": c.textMuted,
  };
}

export function getSentimentConfig(c: ThemeColors): Record<string, { color: string; bg: string }> {
  return {
    "偏多": { color: c.up, bg: `${c.up}1a` },
    "偏空": { color: c.down, bg: `${c.down}1a` },
    "中性": { color: c.accent, bg: `${c.accent}1a` },
  };
}

/* ── 工具函数 ── */

export function getSourceColor(source: string, c: ThemeColors): string {
  if (source.includes("快讯")) return c.warning;
  for (const [key, color] of Object.entries(getSourceColors(c))) {
    if (source.includes(key)) return color;
  }
  return c.textMuted;
}

export function isTwitterItem(item: FeedNewsItem): boolean {
  return item.source === "Twitter" || item.source.includes("𝕏");
}

export function getSourceLabel(source: string, c: ThemeColors): string {
  if (source.includes("快讯")) return "7×24 快讯";
  if (!source) return "未知";
  for (const key of Object.keys(getSourceColors(c))) {
    if (source.includes(key)) return key;
  }
  return source;
}

/* 将原始 source 映射为平台名，用于子 tab 分组 */
const PLATFORM_MAP: Record<string, string> = {
  "东方财富": "东方财富",
  "财联社": "财联社",
  "cnnews": "中国新闻",
  "联合早报": "联合早报",
  "36氪": "36氪",
  "雪球": "雪球",
  "界面新闻": "界面新闻",
  "经济观察报": "经济观察报",
  "华尔街见闻": "华尔街见闻",
  "Twitter": "Twitter",
};

export function getSourcePlatform(source: string): string {
  if (source.includes("快讯")) return "7×24 快讯";
  for (const [key, platform] of Object.entries(PLATFORM_MAP)) {
    if (source.includes(key)) return platform;
  }
  return "其他";
}

export function formatTime(time: string): string {
  if (!time) return "";
  const parsed = parseMarketTime(time);
  if (!parsed) return time;
  const d = dayjs(parsed);
  const diffMin = dayjs().diff(d, "minute");
  if (diffMin < 60) return `${diffMin}分钟前`;
  const diffHour = dayjs().diff(d, "hour");
  if (diffHour < 24) return `${diffHour}小时前`;
  return formatMarketPattern(parsed, "MM-DD HH:mm");
}

export function getTimeColor(time: string, c: ThemeColors): string {
  const parsed = parseMarketTime(time);
  if (!parsed) return c.textMuted;
  const diffMin = dayjs().diff(dayjs(parsed), "minute");
  if (diffMin < 30) return c.warning;
  if (diffMin < 120) return c.textSecondary;
  return c.textMuted;
}

export function clampPage(page: number, totalItems: number, pageSize: number): number {
  if (pageSize <= 0) return 1;
  const totalPages = Math.max(1, Math.ceil(Math.max(0, totalItems) / pageSize));
  return Math.min(Math.max(1, Math.trunc(page)), totalPages);
}

export function getRelativeTimeRefreshDelay(now: number): number {
  const minuteMs = 60_000;
  if (!Number.isFinite(now) || now < 0) return minuteMs;
  const remainder = Math.trunc(now) % minuteMs;
  return remainder === 0 ? minuteMs : minuteMs - remainder;
}
