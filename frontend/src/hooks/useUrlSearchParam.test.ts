import { describe, expect, it } from "vitest";
import { resolveUrlSearchParam, updateUrlSearchParam } from "./useUrlSearchParam";

describe("URL search param helpers", () => {
  it("accepts allowed values and rejects unknown values", () => {
    const allowed = ["overview", "detail"] as const;
    expect(resolveUrlSearchParam("detail", "overview", allowed)).toBe("detail");
    expect(resolveUrlSearchParam("unknown", "overview", allowed)).toBe("overview");
  });

  it("removes default values while preserving other parameters", () => {
    const current = new URLSearchParams("tab=detail&q=bank");
    const next = updateUrlSearchParam(current, "tab", "overview", "overview");
    expect(next.toString()).toBe("q=bank");
  });

  it("sets a non-default value", () => {
    const next = updateUrlSearchParam(new URLSearchParams(), "tab", "detail", "overview");
    expect(next.get("tab")).toBe("detail");
  });
});
