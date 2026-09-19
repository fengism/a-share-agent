import { describe, expect, it } from "vitest";
import {
  buildStockAnalysisUrl,
  buildStockProfileUrl,
  buildWatchlistStockUrl,
  normalizeAshareStockCode,
  normalizeHkStockCode,
  parseStockCode,
} from "./stockLinks";

describe("stockLinks", () => {
  it.each([
    ["601991", "601991"],
    ["SH601991", "601991"],
    ["601991.SH", "601991"],
    [" sz000001 ", "000001"],
  ])("normalizes %s to an A-share code", (input, expected) => {
    expect(normalizeAshareStockCode(input)).toBe(expected);
  });

  it.each([
    "invalid",
    "abc600519xyz",
    "600519-extra",
    "60051",
    "",
  ])("rejects unsupported stock code %s", (input) => {
    expect(normalizeAshareStockCode(input)).toBeNull();
  });

  it.each([
    ["00700", "00700"],
    ["700", "00700"],
    ["HK00700", "00700"],
    ["00700.HK", "00700"],
    [" 9988 ", "09988"],
  ])("normalizes %s to an HK stock code", (input, expected) => {
    expect(normalizeHkStockCode(input)).toBe(expected);
  });

  it.each([
    ["600519", { code: "600519", market: "cn" }],
    ["SH600519", { code: "600519", market: "cn" }],
    ["00700", { code: "00700", market: "hk" }],
    ["700", { code: "00700", market: "hk" }],
    ["HK00700", { code: "00700", market: "hk" }],
    ["00700.HK", { code: "00700", market: "hk" }],
  ])("parses %s to %j", (input, expected) => {
    expect(parseStockCode(input)).toEqual(expected);
  });

  it("builds the in-app stock profile URL", () => {
    expect(buildStockProfileUrl(" 600519 ")).toBe("/stock/600519");
  });

  it("builds the independent stock analysis URL", () => {
    expect(buildStockAnalysisUrl(" 600519 ")).toBe("/analysis/600519");
  });

  it("routes Hong Kong watchlist entries to dedicated stock profile URL", () => {
    expect(buildWatchlistStockUrl("00700", "hk")).toBe("/stock/00700");
    expect(buildWatchlistStockUrl("700", "hk")).toBe("/stock/00700");
    expect(buildWatchlistStockUrl("", "hk")).toBe("/market?market=hk");
    expect(buildWatchlistStockUrl("600519", "cn")).toBe("/stock/600519");
  });
});
