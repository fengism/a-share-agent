import { describe, expect, it } from "vitest";
import { parseDraftStockCodes, STRATEGY_DRAFT_STATUS_META } from "./strategyAuthoring";

describe("strategy authoring helpers", () => {
  it("normalizes mixed separators and removes duplicate stock codes", () => {
    expect(parseDraftStockCodes("600519, 000858，600519\n300750")).toEqual([
      "600519",
      "000858",
      "300750",
    ]);
  });

  it("defines a presentation label for every draft lifecycle state", () => {
    expect(Object.keys(STRATEGY_DRAFT_STATUS_META)).toEqual([
      "draft",
      "validated",
      "testing",
      "backtested",
      "published",
    ]);
  });
});
