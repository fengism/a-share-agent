import { describe, expect, it } from "vitest";
import { normalizeAshareStockCode } from "./stockLinks";

describe("stockLinks", () => {
  it.each([
    ["601991", "601991"],
    ["SH601991", "601991"],
    ["601991.SH", "601991"],
    [" sz000001 ", "000001"],
  ])("normalizes %s to an A-share code", (input, expected) => {
    expect(normalizeAshareStockCode(input)).toBe(expected);
  });

  it("rejects unsupported stock codes", () => {
    expect(normalizeAshareStockCode("invalid")).toBeNull();
  });
});
