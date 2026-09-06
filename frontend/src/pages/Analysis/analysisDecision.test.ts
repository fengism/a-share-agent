import { describe, expect, it } from "vitest";
import type { AnalysisResult } from "../../types/stock";
import { getAnalysisFollowUps, getConditionalAction, getKeyLevelInsight } from "./analysisDecision";

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


describe("key level insight", () => {
  it("calculates distances while price remains inside the key range", () => {
    const insight = getKeyLevelInsight(1520, 1450, 1650);

    expect(insight.status).toBe("within_range");
    expect(insight.label).toBe("区间运行");
    expect(insight.supportDistancePercent).toBeCloseTo(4.8276, 4);
    expect(insight.resistanceDistancePercent).toBeCloseTo(-7.8788, 4);
  });

  it("warns when current price falls below support", () => {
    expect(getKeyLevelInsight(1380, 1450, 1650)).toMatchObject({
      status: "below_support",
      label: "跌破支撑",
      message: "当前价已跌破支撑位，建议重新评估趋势有效性。",
    });
  });

  it("highlights a breakout above resistance", () => {
    expect(getKeyLevelInsight(1700, 1450, 1650)).toMatchObject({
      status: "above_resistance",
      label: "突破压力",
      message: "当前价已突破压力位，关注量价能否持续确认。",
    });
  });

  it.each([
    [undefined, 1450, 1650],
    [1520, Number.NaN, 1650],
    [1520, 1650, 1450],
    [1520, 1500, 1500],
  ])("does not infer a status from unavailable or invalid levels", (current, support, resistance) => {
    expect(getKeyLevelInsight(current, support, resistance)).toEqual({
      status: "unavailable",
      label: "数据待补充",
      message: "关键点位数据不足，暂无法判断当前价格位置。",
      supportDistancePercent: null,
      resistanceDistancePercent: null,
    });
  });
});
