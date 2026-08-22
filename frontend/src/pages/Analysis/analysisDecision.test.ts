import { describe, expect, it } from "vitest";
import type { AnalysisResult } from "../../types/stock";
import { getAnalysisFollowUps, getConditionalAction } from "./analysisDecision";

describe("analysis decision copy", () => {
  it("uses conditional research language instead of direct trading instructions", () => {
    expect(getConditionalAction("buy")).toMatchObject({ label: "关注", tone: "positive" });
    expect(getConditionalAction("hold")).toMatchObject({ label: "观察", tone: "neutral" });
    expect(getConditionalAction("sell")).toMatchObject({ label: "谨慎", tone: "negative" });
  });

  it("builds contextual follow-up prompts", () => {
    const prompts = getAnalysisFollowUps({ stock_code: "600519", stock_name: "贵州茅台", signal: "hold" } as AnalysisResult);
    expect(prompts).toHaveLength(5);
    expect(prompts[0]).toContain("贵州茅台");
    expect(prompts[0]).toContain("观察");
    expect(prompts[1]).toContain("失效条件");
  });
});
