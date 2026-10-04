import { useEffect, useMemo, useState } from "react";

/** 指数区间档位：与个股页 K 线的历史窗口习惯一致，最大 10 年。 */
export const CONCEPT_INDEX_RANGES = [
  { label: "3月", days: 90 },
  { label: "1年", days: 365 },
  { label: "3年", days: 1095 },
  { label: "5年", days: 1825 },
  { label: "10年", days: 3650 },
] as const;

export const DEFAULT_INDEX_DAYS = 365;

/**
 * 概念选择状态：优先读 URL 上的 ``?concept=``，这样从相关概念点进来可以分享链接。
 */
export function useConceptParam(): [string, (next: string) => void] {
  const [param, setParam] = useState(
    () => new URLSearchParams(window.location.search).get("concept") ?? "",
  );

  useEffect(() => {
    const onPopState = () => {
      setParam(new URLSearchParams(window.location.search).get("concept") ?? "");
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, []);

  const setConcept = (next: string) => {
    const url = new URL(window.location.href);
    if (next) {
      url.searchParams.set("concept", next);
    } else {
      url.searchParams.delete("concept");
    }
    window.history.replaceState(null, "", url);
    setParam(next);
  };

  return [param, setConcept];
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