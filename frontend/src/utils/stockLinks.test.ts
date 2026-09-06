import { describe, expect, it } from "vitest";
import {
  buildStockAnalysisUrl,
  buildStockProfileUrl,
  buildWatchlistStockUrl,
  normalizeAshareStockCode,
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

  it("builds the in-app stock profile URL", () => {
    expect(buildStockProfileUrl(" 600519 ")).toBe("/stock/600519");
  });

  it("builds the independent stock analysis URL", () => {
    expect(buildStockAnalysisUrl(" 600519 ")).toBe("/analysis/600519");
  });

  it("keeps Hong Kong watchlist entries on the Hong Kong market page with optional code param", () => {
    expect(buildWatchlistStockUrl("00700", "hk")).toBe("/market?market=hk&code=00700");
    expect(buildWatchlistStockUrl("", "hk")).toBe("/market?market=hk");
    expect(buildWatchlistStockUrl("600519", "cn")).toBe("/stock/600519");
  });
});
