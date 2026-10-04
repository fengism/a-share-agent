import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CONCEPT_INDEX_RANGES, DEFAULT_INDEX_DAYS, useConceptSearch } from "./conceptSelection";

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