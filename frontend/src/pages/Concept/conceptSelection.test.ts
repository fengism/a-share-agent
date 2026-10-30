import { renderHook, waitFor } from "@testing-library/react";
import { act } from "react";
import { afterEach, describe, expect, it } from "vitest";

import {
  CONCEPT_INDEX_RANGES,
  DEFAULT_INDEX_DAYS,
  limitUpBadge,
  useConceptPageParams,
  useConceptSearch,
  useFavoriteConcepts,
  useRecentConcepts,
} from "./conceptSelection";

describe("conceptSelection", () => {
  it("offers ranges from 3 months up to the 10 year data ceiling", () => {
    const days = CONCEPT_INDEX_RANGES.map((range) => range.days);
    expect(days).toEqual([90, 365, 1095, 1825, 3650]);
    expect(DEFAULT_INDEX_DAYS).toBe(365);
    // 后端 days 上限 3650，前端不能给出越界档位，否则会拿到 422
    expect(Math.max(...days)).toBeLessThanOrEqual(3650);
  });
});

describe("useConceptSearch", () => {
  const items = [
    { name: "机器人概念" },
    { name: "人形机器人" },
    { name: "固态电池" },
    { name: "DeepSeek概念" },
  ];

  const search = (keyword: string) =>
    renderHook(() => useConceptSearch(items, keyword)).result.current.map((item) => item.name);

  it("returns everything for a blank keyword", () => {
    expect(search("")).toHaveLength(4);
    expect(search("   ")).toHaveLength(4);
  });

  it("matches concept names case-insensitively", () => {
    expect(search("机器人")).toEqual(["机器人概念", "人形机器人"]);
    expect(search("deepseek")).toEqual(["DeepSeek概念"]);
  });

  it("returns an empty list when nothing matches", () => {
    expect(search("不存在的概念")).toEqual([]);
  });
});

describe("useConceptPageParams", () => {
  afterEach(() => {
    window.history.replaceState(null, "", "/concept");
  });

  it("writes the concept to the URL and keeps it readable back", async () => {
    const { result } = renderHook(() => useConceptPageParams());
    const [, patch] = result.current;

    act(() => patch({ concept: "固态电池" }));

    expect(result.current[0]).toEqual({ concept: "固态电池", days: DEFAULT_INDEX_DAYS, compare: [] });
    expect(window.location.search).toContain("concept=%E5%9B%BA%E6%80%81%E7%94%B5%E6%B1%A0");

    // 浏览器后退（popstate）回到无参数状态：换概念用 pushState，后退键可用
    act(() => {
      window.history.back();
    });
    await waitFor(() => expect(result.current[0].concept).toBe(""));
  });

  it("persists the range in the URL but omits the default range", () => {
    const { result } = renderHook(() => useConceptPageParams());
    const [, patch] = result.current;

    act(() => patch({ days: 90 }));
    expect(result.current[0].days).toBe(90);
    expect(window.location.search).toContain("days=90");

    act(() => patch({ days: 365 }));
    expect(result.current[0].days).toBe(365);
    expect(window.location.search).not.toContain("days=");

    // 非法档位回落默认值，避免把越界值传给后端拿 422
    window.history.replaceState(null, "", "/concept?days=777");
    const reread = renderHook(() => useConceptPageParams());
    expect(reread.result.current[0].days).toBe(DEFAULT_INDEX_DAYS);
  });
});

describe("useFavoriteConcepts", () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  it("toggles favorites and persists them", () => {
    const { result } = renderHook(() => useFavoriteConcepts());
    const { toggle } = result.current;

    act(() => toggle("固态电池"));
    expect(result.current.favorites).toEqual(["固态电池"]);
    expect(result.current.has("固态电池")).toBe(true);

    act(() => toggle("固态电池"));
    expect(result.current.favorites).toEqual([]);
    expect(result.current.has("固态电池")).toBe(false);
    // 持久化到 localStorage
    expect(JSON.parse(window.localStorage.getItem("concept.favorite_names") || "[]")).toEqual([]);
  });
});

describe("useRecentConcepts", () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  it("remembers viewed concepts with the latest first and deduplicates", () => {
    const { result } = renderHook(() => useRecentConcepts());
    const [, remember] = result.current;

    act(() => remember("固态电池"));
    act(() => remember("机器人概念"));
    act(() => remember("固态电池"));

    expect(result.current[0]).toEqual(["固态电池", "机器人概念"]);
    // 持久化到 localStorage，下次进页面还在
    const stored = JSON.parse(window.localStorage.getItem("concept.recent_names") || "[]") as string[];
    expect(stored).toEqual([
      "固态电池",
      "机器人概念",
    ]);
  });

  it("caps the list at 8 entries", () => {
    const { result } = renderHook(() => useRecentConcepts());
    const [, remember] = result.current;

    act(() => {
      for (let i = 1; i <= 10; i += 1) remember(`概念${i}`);
    });

    expect(result.current[0]).toHaveLength(8);
    expect(result.current[0][0]).toBe("概念10");
  });
});

describe("limitUpBadge", () => {
  it("uses board-specific limit thresholds", () => {
    // 主板 10% 档
    expect(limitUpBadge("000001", 9.98)).toBe("up");
    expect(limitUpBadge("600519", -9.95)).toBe("down");
    // 创业板/科创板 20% 档：9.98% 只是普涨
    expect(limitUpBadge("300750", 9.98)).toBeNull();
    expect(limitUpBadge("688981", 19.92)).toBe("up");
    // 北交所 30% 档（含新 920 号段与老 8x/4x 号段）
    expect(limitUpBadge("832566", 29.9)).toBe("up");
    expect(limitUpBadge("920001", 15.0)).toBeNull();
    expect(limitUpBadge("920001", 29.9)).toBe("up");
    // 无行情不判断
    expect(limitUpBadge("000001", null)).toBeNull();
  });
});
