import { describe, expect, it } from "vitest";
import {
  parseQuantStockCodes,
  selectQuantBacktestFromAuthoring,
  selectQuantResult,
  selectQuantTask,
} from "./quantUrlState";

describe("quant URL state", () => {
  it("normalizes, deduplicates and limits prefilled stock codes", () => {
    const input = ["600519", "000001", "600519", "bad", "000002", "000003", "000004", "000005", "000006", "000007", "000008", "000009"];
    expect(parseQuantStockCodes(new URLSearchParams({ codes: input.join(",") }))).toEqual([
      "600519", "000001", "000002", "000003", "000004", "000005", "000006", "000007", "000008", "000009",
    ]);
  });

  it("returns an authoring run to backtesting without dropping unrelated parameters", () => {
    const current = new URLSearchParams("view=authoring&codes=600519%2C000858&run=old-run");

    const next = selectQuantBacktestFromAuthoring(current, "draft-run");

    expect(next.get("run")).toBe("draft-run");
    expect(next.get("panel")).toBe("runs");
    expect(next.get("view")).toBeNull();
    expect(next.get("codes")).toBe("600519,000858");
    expect(current.get("view")).toBe("authoring");
  });

  it("selects a completed run and its result panel atomically", () => {
    const next = selectQuantResult(new URLSearchParams("run=old&panel=runs&codes=600519"), "new-run");

    expect(next.get("run")).toBe("new-run");
    expect(next.get("panel")).toBe("result");
    expect(next.get("codes")).toBe("600519");
  });

  it("selects a newly created run and its task panel atomically", () => {
    const next = selectQuantTask(new URLSearchParams("panel=setup&codes=600519"), "new-run");

    expect(next.get("run")).toBe("new-run");
    expect(next.get("panel")).toBe("runs");
    expect(next.get("codes")).toBe("600519");
  });
});
