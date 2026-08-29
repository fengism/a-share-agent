import { describe, expect, it } from "vitest";
import { buildAnalysisHistoryUrl, normalizeAnalysisDate } from "./analysisHistoryUrl";

describe("analysis history URL", () => {
  it("keeps the selected history date in the analysis URL", () => {
    expect(buildAnalysisHistoryUrl("600519", "20260807")).toBe("/analysis/600519?date=20260807");
  });

  it("builds history links for an injected route base", () => {
    expect(buildAnalysisHistoryUrl("600519", "2026-08-07", "/investment-research"))
      .toBe("/investment-research/600519?date=20260807");
  });

  it("normalizes compact and ISO history dates while rejecting impossible dates", () => {
    expect(normalizeAnalysisDate("20260807")).toBe("20260807");
    expect(normalizeAnalysisDate("2026-08-07")).toBe("20260807");
    expect(normalizeAnalysisDate("20260230")).toBe("");
    expect(normalizeAnalysisDate(null)).toBe("");
  });
});
