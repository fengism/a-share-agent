import { describe, expect, it } from "vitest";
import { buildAnalysisHistoryUrl, normalizeAnalysisDate } from "./analysisHistoryUrl";

describe("analysis history URL", () => {
  it("keeps the selected history date in the analysis URL", () => {
    expect(buildAnalysisHistoryUrl("600519", "20260807")).toBe("/analysis/600519?date=20260807");
  });

  it("accepts only YYYYMMDD history dates", () => {
    expect(normalizeAnalysisDate("20260807")).toBe("20260807");
    expect(normalizeAnalysisDate("2026-08-07")).toBe("");
    expect(normalizeAnalysisDate(null)).toBe("");
  });
});
