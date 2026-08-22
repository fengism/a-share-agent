import { describe, expect, it } from "vitest";
import { DEFAULT_INDUSTRY_SCOPE, validateIndustryScope } from "./industryScope";

describe("industry research scope", () => {
  it("keeps the simple workflow valid by default", () => {
    expect(validateIndustryScope(DEFAULT_INDUSTRY_SCOPE)).toBe("");
  });

  it("requires an ordered custom date range", () => {
    expect(validateIndustryScope({
      ...DEFAULT_INDUSTRY_SCOPE,
      time_range: "custom",
      start_date: "2026-08-18",
      end_date: "2026-08-01",
    })).toContain("开始日期");
  });
});
