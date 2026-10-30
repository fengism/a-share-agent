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

export interface ClusteredNewsItem extends FeedNewsItem {
  otherSources?: string[];
}

export function cleanNewsTitle(title: string): string {
  let cleaned = (title || "").trim();
  if (!cleaned) return "";

  // 循环剥离前导方头括号或方括号内容，如 【快讯】、【财联社4月15日电】、[最新消息]
  while (cleaned) {
    const match = cleaned.match(/^(?:【[^】]*】|\[[^\]]*\])\s*/);
    if (!match) break;
    cleaned = cleaned.slice(match[0].length).trim();
  }

  // 剥离通讯社电讯前缀，如 "财联社4月15日电 "、"新华社北京4月15日电 "、"证券时报网讯 "
  cleaned = cleaned.replace(/^[\u4e00-\u9fa5]{2,10}(?:网|报|社|电讯|财经)?\s*(?:\d{1,2}月\d{1,2}日)?\s*[电讯]\s*[:：，,\s]*/, "").trim();

  // 剥离末尾括号来源，如 "（新浪财经）"、"(财联社)"、"（来源：证券时报）"
  cleaned = cleaned.replace(/[（(](?:来源[：:])?[\u4e00-\u9fa5a-zA-Z0-9_\-\s]{2,16}[）)]\s*$/, "").trim();

  // 剥离末尾破折号/下划线来源，如 "- 华尔街见闻"、"—— 东方财富网"
  cleaned = cleaned.replace(/[-—_~]+\s*[\u4e00-\u9fa5a-zA-Z0-9]{2,12}(?:网|财经|报|社)?\s*$/, "").trim();

  return cleaned;
}

export function normalizeNewsTitle(title: string): string {
  const cleaned = cleanNewsTitle(title);
  return cleaned.toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
}

export function computeHeadlineSimilarity(s1: string, s2: string): number {
  if (!s1 || !s2) return 0;
  if (s1 === s2) return 1;
  const m = s1.length;
  const n = s2.length;
  const dp = new Array(n + 1).fill(0);
  for (let i = 0; i < m; i++) {
    let prev = 0;
    const ch1 = s1[i];
    for (let j = 1; j <= n; j++) {
      const temp = dp[j];
      if (ch1 === s2[j - 1]) {
        dp[j] = prev + 1;
      } else {
        dp[j] = Math.max(dp[j], dp[j - 1]);
      }
      prev = temp;
    }
  }
  return (2 * dp[n]) / (m + n);
}

export function clusterNewsItems(items: FeedNewsItem[], dedupeEnabled: boolean): ClusteredNewsItem[] {
  if (!dedupeEnabled || items.length <= 1) {
    return items;
  }

  const result: ClusteredNewsItem[] = [];
  const normalizedList: string[] = [];

  for (const item of items) {
    const rawTitle = item.title || "";
    const norm = normalizeNewsTitle(rawTitle);

    if (!norm) {
      result.push(item);
      continue;
    }

    let matchedIdx = -1;
    for (let i = 0; i < normalizedList.length; i++) {
      const existingNorm = normalizedList[i];
      if (existingNorm === norm) {
        matchedIdx = i;
        break;
      }
      if (norm.length >= 8 && existingNorm.length >= 8) {
        const lenRatio = norm.length / Math.max(1, existingNorm.length);
        if (lenRatio >= 0.6 && lenRatio <= 1.67) {
          if (computeHeadlineSimilarity(norm, existingNorm) >= 0.8) {
            matchedIdx = i;
            break;
          }
        }
      }
    }

    if (matchedIdx >= 0) {
      const parent = result[matchedIdx];
      const sourceName = item.source || "其他";
      const existingSources = parent.otherSources || [];
      if (sourceName !== parent.source && !existingSources.includes(sourceName)) {
        parent.otherSources = [...existingSources, sourceName];
      }
      if (!parent.content && item.content) {
        parent.content = item.content;
      }
      if (!parent.image_url && item.image_url) {
        parent.image_url = item.image_url;
      }
    } else {
      const cloned: ClusteredNewsItem = { ...item };
      result.push(cloned);
      normalizedList.push(norm);
    }
  }

  return result;
}
