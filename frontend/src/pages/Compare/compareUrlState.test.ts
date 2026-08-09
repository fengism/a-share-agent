import { describe, expect, it } from "vitest";
import { parseCompareCodes, serializeCompareCodes } from "./compareUrlState";

describe("compare URL state", () => {
  it("keeps unique six-digit stock codes", () => {
    expect(parseCompareCodes("600519,invalid,300750,600519")).toEqual(["600519", "300750"]);
  });

  it("serializes normalized codes", () => {
    expect(serializeCompareCodes([" 600519 ", "300750", "600519"])).toBe("600519,300750");
  });

  it("limits comparison state to five stocks", () => {
    expect(parseCompareCodes("000001,000002,000003,000004,000005,000006")).toEqual([
      "000001", "000002", "000003", "000004", "000005",
    ]);
  });
});
