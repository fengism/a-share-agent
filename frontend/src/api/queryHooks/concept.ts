import { useQuery } from "@tanstack/react-query";
import { openApiGet } from "../openapiClient";
import { QUERY_CACHE_POLICIES } from "../cachePolicies";
import { queryKeys } from "../queryKeys";
import type { components } from "../generated/schema";

export type ConceptSummary = components["schemas"]["ConceptSummaryItem"];
export type ConceptConstituent = components["schemas"]["ConceptConstituentItem"];
export type RelatedConcept = components["schemas"]["RelatedConceptItem"];
export type ConceptConstituentResult = components["schemas"]["ConceptConstituentResponse"];
export type ConceptIndexPoint = components["schemas"]["ConceptIndexPoint"];
export type ConceptIndexResult = components["schemas"]["ConceptIndexResponse"];

/** 概念选择器列表。概念有 1100+ 个，一次拉全量后前端本地搜索，避免每次输入都打接口。 */
export function useConceptList(limit = 1200) {
  return useQuery({
    queryKey: queryKeys.market.concepts(limit),
    queryFn: () =>
      openApiGet("/api/market/concepts", {
        query: { limit },
      }),
    staleTime: QUERY_CACHE_POLICIES.marketRealtime.staleMs,
  });
}

export function useConceptConstituents(concept: string, quoteCodes?: string[]) {
  // 按需加载时把代码集并入 key：不同窗口是不同结果，避免缓存串味。
  const codesKey = quoteCodes && quoteCodes.length ? [...quoteCodes].sort().join(",") : "";
  return useQuery({
    queryKey: [...queryKeys.market.conceptConstituents(concept), codesKey],
    queryFn: () =>
      openApiGet("/api/market/concept/{concept}/constituents", {
        path: { concept },
        query: quoteCodes && quoteCodes.length ? { codes: codesKey } : {},
      }),
    enabled: Boolean(concept),
    // 成分股身份是低频数据，但行情要新；沿用市场实时缓存档位
    staleTime: QUERY_CACHE_POLICIES.marketRealtime.staleMs,
    // 换概念时保留上一批成分股，避免上千行表格先塌成骨架屏再重排
    placeholderData: (previous) => previous,
  });
}

/**
 * 本地合成的等权概念指数。
 *
 * 合成本身在后端用 SQL 完成（1 年约 0.4s），并按 concept+days 缓存 6 小时，
 * 所以这里给较长的 staleTime，避免翻区间时反复打接口。
 */
export function useConceptIndex(concept: string, days: number) {
  return useQuery({
    queryKey: queryKeys.market.conceptIndex(concept, days),
    queryFn: () =>
      openApiGet("/api/market/concept/{concept}/index", {
        path: { concept },
        query: { days },
      }),
    enabled: Boolean(concept),
    staleTime: QUERY_CACHE_POLICIES.conceptIndex.staleMs,
    // 切换区间/概念时保留上一批数据：长区间首次合成本身要几秒，
    // 若让 data 变undefined 会把图表换成骨架屏，视觉上像"白屏重载"。
    placeholderData: (previous) => previous,
  });
}