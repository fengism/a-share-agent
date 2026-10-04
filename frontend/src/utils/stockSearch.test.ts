import { describe, expect, it } from "vitest";
import {
  excludeStockSearchResults,
  getCurrentStockSearchResults,
  normalizeStockSearchInput,
  resolveStockSearchCode,
} from "./stockSearch";

describe("stock search helpers", () => {
  it("normalizes surrounding whitespace", () => {
    expect(normalizeStockSearchInput("  贵州茅台  ")).toBe("贵州茅台");
  });

  it("uses a six-digit code without waiting for results", () => {
    expect(resolveStockSearchCode(" 600519 ", "", [])).toBe("600519");
  });

  it("uses a 5-digit HK code or HK prefix code without waiting for results", () => {
    expect(resolveStockSearchCode(" 00700 ", "", [])).toBe("00700");
    expect(resolveStockSearchCode("HK00700", "", [])).toBe("00700");
  });

  it("rejects results belonging to an older query", () => {
    expect(resolveStockSearchCode("宁德时代", "贵州茅台", [{ code: "600519" }])).toBeNull();
  });

  it("uses the first result for the current query", () => {
    expect(resolveStockSearchCode("贵州茅台", "贵州茅台", [{ code: "600519" }])).toBe("600519");
  });

  it("publishes results only for the current normalized input", () => {
    const results = [{ code: "600519" }];
    expect(getCurrentStockSearchResults("贵州茅台", "贵州茅台", results)).toBe(results);
    expect(getCurrentStockSearchResults("宁德时代", "贵州茅台", results)).toEqual([]);
  });

  it("filters already selected codes without changing the source array", () => {
    const results = [{ code: "600519" }, { code: "300750" }];
    expect(excludeStockSearchResults(results, ["600519"])).toEqual([{ code: "300750" }]);
    expect(results).toHaveLength(2);
  });
});
