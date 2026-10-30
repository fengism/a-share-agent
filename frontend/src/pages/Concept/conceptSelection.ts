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
