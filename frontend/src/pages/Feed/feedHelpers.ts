import dayjs from "dayjs";
import type { FeedNewsItem } from "../../types/stock";
import type { ThemeColors } from "../../theme/themes";

/* ── 配色常量 ── */
export const KUAIXUN_ACCENT = "#f59e0b";
export const KUAIXUN_ACCENT_BG = "rgba(245,158,11,0.08)";

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
  if (source.includes("快讯")) return KUAIXUN_ACCENT;
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
  const d = dayjs(time);
  if (!d.isValid()) return time;
  const diffMin = dayjs().diff(d, "minute");
  if (diffMin < 60) return `${diffMin}分钟前`;
  const diffHour = dayjs().diff(d, "hour");
  if (diffHour < 24) return `${diffHour}小时前`;
  return d.format("MM-DD HH:mm");
}

export function getTimeColor(time: string, c: ThemeColors): string {
  const d = dayjs(time);
  if (!d.isValid()) return c.textMuted;
  const diffMin = dayjs().diff(d, "minute");
  if (diffMin < 30) return KUAIXUN_ACCENT;
  if (diffMin < 120) return c.textSecondary;
  return "#64748b";
}
