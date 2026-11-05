import { useCallback, useEffect, useMemo, useState } from "react";

/** 指数区间档位：与个股页 K 线的历史窗口习惯一致，最大 10 年。 */
export const CONCEPT_INDEX_RANGES = [
  { label: "3月", days: 90 },
  { label: "1年", days: 365 },
  { label: "3年", days: 1095 },
  { label: "5年", days: 1825 },
  { label: "10年", days: 3650 },
] as const;

export const DEFAULT_INDEX_DAYS = 365;

const CONCEPT_PARAM = "concept";
const DAYS_PARAM = "days";
/** 对比概念（叠加走势），逗号分隔，最多 2 个（加上当前概念共 3 条线） */
const COMPARE_PARAM = "compare";
export const COMPARE_CONCEPT_LIMIT = 2;

/** 最近查看的概念：localStorage 持久化，最多保留 8 个。 */
const RECENT_CONCEPTS_KEY = "concept.recent_names";
const RECENT_CONCEPTS_LIMIT = 8;

/** 收藏（关注）的概念：localStorage 持久化，最多保留 20 个。 */
const FAVORITE_CONCEPTS_KEY = "concept.favorite_names";
const FAVORITE_CONCEPTS_LIMIT = 20;

function readStoredNames(key: string): string[] {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is string => typeof item === "string" && item.length > 0);
  } catch {
    return [];
  }
}

function saveStoredNames(key: string, names: string[]) {
  try {
    window.localStorage.setItem(key, JSON.stringify(names));
  } catch {
    // 隐私模式等场景下 localStorage 不可用时静默降级：收藏/最近只是锦上添花
  }
}

export function readRecentConcepts(): string[] {
  return readStoredNames(RECENT_CONCEPTS_KEY);
}

export function useRecentConcepts(): [string[], (name: string) => void] {
  const [recent, setRecent] = useState<string[]>(() => readRecentConcepts());

  const remember = useCallback((name: string) => {
    if (!name) return;
    setRecent((prev) => {
      const next = [name, ...prev.filter((item) => item !== name)].slice(0, RECENT_CONCEPTS_LIMIT);
      saveStoredNames(RECENT_CONCEPTS_KEY, next);
      return next;
    });
  }, []);

  return [recent, remember];
}

export interface FavoriteConceptsApi {
  favorites: string[];
  has: (name: string) => boolean;
  toggle: (name: string) => void;
}

export function useFavoriteConcepts(): FavoriteConceptsApi {
  const [favorites, setFavorites] = useState<string[]>(() => readStoredNames(FAVORITE_CONCEPTS_KEY));

  const toggle = useCallback((name: string) => {
    if (!name) return;
    setFavorites((prev) => {
      const next = prev.includes(name)
        ? prev.filter((item) => item !== name)
        : [name, ...prev].slice(0, FAVORITE_CONCEPTS_LIMIT);
      saveStoredNames(FAVORITE_CONCEPTS_KEY, next);
      return next;
    });
  }, []);

  const favoriteSet = useMemo(() => new Set(favorites), [favorites]);
  const has = useCallback((name: string) => favoriteSet.has(name), [favoriteSet]);

  return { favorites, has, toggle };
}

function readPageParams(): { concept: string; days: number; compare: string[] } {
  const search = new URLSearchParams(window.location.search);
  const concept = search.get(CONCEPT_PARAM) ?? "";
  const rawDays = Number(search.get(DAYS_PARAM));
  const days = CONCEPT_INDEX_RANGES.some((range) => range.days === rawDays)
    ? rawDays
    : DEFAULT_INDEX_DAYS;
  const compare = (search.get(COMPARE_PARAM) ?? "")
    .split(",")
    .map((name) => name.trim())
    .filter(Boolean)
    .slice(0, COMPARE_CONCEPT_LIMIT);
  return { concept, days, compare };
}

/**
 * 概念页 URL 状态：``?concept=`` / ``?days=`` / ``?compare=``。
 *
 * 用 pushState 而非 replaceState：概念/档位切换后浏览器后退能回到上一个视图，
 * 链接可直接分享（含指数区间档位与对比组合）。不用 react-router 的 useSearchParams，
 * 因为路由器感知不到这里直接操作 history 的概念切换，反而会用旧地址覆盖掉 concept 参数。
 */
export function useConceptPageParams(): [
  { concept: string; days: number; compare: string[] },
  (patch: { concept?: string; days?: number; compare?: string[] }) => void,
] {
  const [params, setParams] = useState(readPageParams);

  useEffect(() => {
    const onPopState = () => {
      setParams(readPageParams());
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const patch = useCallback((next: { concept?: string; days?: number; compare?: string[] }) => {
    const url = new URL(window.location.href);
    if (next.concept !== undefined) {
      if (next.concept) url.searchParams.set(CONCEPT_PARAM, next.concept);
      else url.searchParams.delete(CONCEPT_PARAM);
    }
    if (next.days !== undefined) {
      if (next.days !== DEFAULT_INDEX_DAYS) url.searchParams.set(DAYS_PARAM, String(next.days));
      else url.searchParams.delete(DAYS_PARAM);
    }
    if (next.compare !== undefined) {
      const names = next.compare.filter(Boolean).slice(0, COMPARE_CONCEPT_LIMIT);
      if (names.length) url.searchParams.set(COMPARE_PARAM, names.join(","));
      else url.searchParams.delete(COMPARE_PARAM);
    }
    window.history.pushState(null, "", url);
    setParams(readPageParams());
  }, []);

  return [params, patch];
}

export const COMMON_CONCEPT_ALIASES: Record<string, string> = {
  "光伏": "光伏概念",
  "芯片": "芯片概念",
  "半导体": "半导体",
  "新能源车": "新能源汽车",
  "新能源汽车": "新能源汽车",
  "锂电": "锂电池概念",
  "锂电池": "锂电池概念",
  "白酒": "白酒概念",
  "机器人": "机器人概念",
  "商业航天": "商业航天",
  "航天": "商业航天",
  "算力": "东数西算(算力)",
  "AI算力": "算力租赁",
  "人形机器人": "人形机器人",
  "消费电子": "消费电子概念",
  "低空经济": "低空经济",
  "无人驾驶": "无人驾驶",
  "智能驾驶": "无人驾驶",
  "信创": "信创",
  "央企改革": "央企国企改革",
  "军工": "军工",
  "固态电池": "固态电池",
};

/**
 * 概念名称规范化与智能别名映射：
 * 将今日主线（财联社等不同上游）、外部链接或用户简称（如「光伏」、「芯片」）
 * 映射至本地同花顺维护的概念标准名（如「光伏概念」、「芯片概念」）。
 */
export function resolveConceptName<T extends { name: string; stock_count?: number }>(
  input: string,
  conceptList: T[],
): string {
  if (!input || !conceptList.length) return input;
  const trimmed = input.trim();
  // 1. 精确匹配
  const exact = conceptList.find((c) => c.name === trimmed);
  if (exact) return exact.name;

  // 2. 常见行业/主线宏观题材至同花顺概念的映射表
  if (COMMON_CONCEPT_ALIASES[trimmed]) {
    const aliasTarget = COMMON_CONCEPT_ALIASES[trimmed];
    const aliasMatch = conceptList.find((c) => c.name === aliasTarget);
    if (aliasMatch) return aliasMatch.name;
  }

  // 3. 概念后缀增删：「光伏」->「光伏概念」，或「光伏概念」->「光伏」
  if (!trimmed.endsWith("概念")) {
    const withConcept = conceptList.find((c) => c.name === `${trimmed}概念`);
    if (withConcept) return withConcept.name;
  } else {
    const withoutConcept = conceptList.find((c) => c.name === trimmed.slice(0, -2));
    if (withoutConcept) return withoutConcept.name;
  }

  // 4. 前缀匹配：选取以 trimmed 开头且成分股最多的板块（例如「光伏」前缀中规模最大的「光伏概念」）
  const prefixMatches = conceptList
    .filter((c) => c.name.startsWith(trimmed))
    .sort((a, b) => (b.stock_count ?? 0) - (a.stock_count ?? 0));
  if (prefixMatches.length > 0) return prefixMatches[0].name;

  // 5. 包含匹配：包含关键字且成分股最多的板块
  const includesMatches = conceptList
    .filter((c) => c.name.includes(trimmed))
    .sort((a, b) => (b.stock_count ?? 0) - (a.stock_count ?? 0));
  if (includesMatches.length > 0) return includesMatches[0].name;

  return trimmed;
}

/** 概念搜索：本地过滤，避免每敲一个字就打接口。泛型保留 stock_count 等附加字段。 */
export function useConceptSearch<T extends { name: string }>(items: T[], keyword: string): T[] {
  return useMemo(() => {
    const text = keyword.trim();
    if (!text) return items;
    const lower = text.toLowerCase();
    return items.filter((item) => item.name.toLowerCase().includes(lower));
  }, [items, keyword]);
}

/**
 * 涨停/跌停判断：不同板块的涨跌幅限制不同，按代码前缀区分档位
 * （主板 10%、创业板/科创板 20%、北交所 30%）。ST 股 5% 的情形不识别，
 * 宁可漏标也不误标。
 */
export function changeLimitPct(code: string): number {
  if (code.startsWith("30") || code.startsWith("68")) return 19.8;
  if (code.startsWith("8") || code.startsWith("4") || code.startsWith("920")) return 29.8;
  return 9.8;
}

export function limitUpBadge(code: string, changePct: number | null | undefined): "up" | "down" | null {
  if (changePct == null) return null;
  const limit = changeLimitPct(code);
  if (changePct >= limit) return "up";
  if (changePct <= -limit) return "down";
  return null;
}
