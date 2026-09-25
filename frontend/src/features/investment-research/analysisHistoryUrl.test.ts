import { describe, expect, it } from "vitest";
import { buildStockValuationUrl } from "./analysisHistoryUrl";

describe("buildStockValuationUrl", () => {
  it("links directly to the profile valuation section", () => {
    expect(buildStockValuationUrl(" 600519 ")).toBe("/stock/600519?tab=valuation#stock-details");
  });
  it("preserves a normalized historical date", () => {
    expect(buildStockValuationUrl("600519", "2026-08-20")).toBe("/stock/600519?tab=valuation&date=20260820#stock-details");
  });
  it("does not forward invalid historical dates", () => {
    expect(buildStockValuationUrl("600519", "20260231")).toBe("/stock/600519?tab=valuation#stock-details");
  });
});
