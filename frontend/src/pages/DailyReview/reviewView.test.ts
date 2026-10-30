import { describe, expect, it } from "vitest";
import {
  buildCheckAccuracy,
  buildMoodSummary,
  buildReviewHeadline,
  buildReviewSections,
  formatSignedPct,
  stageTone,
  type DailyReviewPayload,
} from "./reviewView";

function makeReview(overrides: Record<string, unknown> = {}): DailyReviewPayload {
  return {
    date: "2026-10-29",
    title: "每日复盘",
    market_summary: "指数震荡，主线分化。",
    data_snapshot: {
      indices: [{ name: "上证指数", change_pct: 0.85 }],
      hot_stocks: [],
      hot_concepts: [],
      hot_industries: [],
      dragon_tiger: [],
      top_sectors: [{ name: "机器人" }],
      bottom_sectors: [{ name: "白酒" }],
      market_statistics: { limit_up_count: 42, break_rate: 0.18 },
    },
    ...overrides,
  } as unknown as DailyReviewPayload;
}

describe("reviewView", () => {
  it("builds a mood summary from indices and sector extremes", () => {
    expect(buildMoodSummary(makeReview())).toContain("指数偏强");
    expect(buildMoodSummary(makeReview())).toContain("机器人");
  });

  it("extracts headline metrics including percentage normalisation", () => {
    const headline = buildReviewHeadline(
      makeReview({
        sentiment_cycle: { stage: "分歧转一致" },
        previous_review_check: { checked_count: 4, hit_count: 3 },
      }),
    );

    expect(headline.limitUpCount).toBe(42);
    // 0.18 视为比例 → 18%
    expect(headline.breakRate).toBeCloseTo(18);
    expect(headline.indexChangePct).toBeCloseTo(0.85);
    expect(headline.stage).toBe("分歧转一致");
    expect(headline.checkHit).toBe(3);
    expect(headline.checkTotal).toBe(4);
    expect(headline.quality).toBe("complete");
    expect(headline.generation).toBe("ai");
  });

  it("marks degraded quality and fallback generation", () => {
    const headline = buildReviewHeadline(
      makeReview({ quality_status: "degraded", generation_status: "fallback" }),
    );

    expect(headline.quality).toBe("degraded");
    expect(headline.generation).toBe("fallback");
  });

  it("lists only available sections with their counts", () => {
    const sections = buildReviewSections(
      makeReview({
        scenario_plans: [{ name: "乐观" }, { name: "中性" }],
        key_levels: ["沪指 3200"],
      }),
    );

    const ids = sections.map((section) => section.id);
    expect(ids).toContain("review-charts");
    expect(ids).toContain("review-scenarios");
    expect(ids).toContain("review-key-levels");
    expect(ids).not.toContain("review-policy");
    expect(sections.find((s) => s.id === "review-scenarios")?.count).toBe(2);
  });

  it("computes self-check accuracy and handles missing samples", () => {
    expect(
      buildCheckAccuracy(makeReview({ previous_review_check: { checked_count: 4, hit_count: 3 } })),
    ).toBeCloseTo(0.75);
    expect(buildCheckAccuracy(makeReview())).toBeNull();
  });

  it("maps stages to semantic tones", () => {
    expect(stageTone("高潮")).toBe("up");
    expect(stageTone("退潮")).toBe("down");
    expect(stageTone("分歧")).toBe("warning");
    expect(stageTone(undefined)).toBe("neutral");
  });

  it("formats signed percentages", () => {
    expect(formatSignedPct(3.2)).toBe("+3.20%");
    expect(formatSignedPct(-1.5)).toBe("-1.50%");
    expect(formatSignedPct(null)).toBe("—");
  });
});
