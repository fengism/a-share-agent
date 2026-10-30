import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import DailyReviewHero from "./DailyReviewHero";
import { buildReviewHeadline, type DailyReviewPayload } from "./reviewView";

function makeReview(overrides: Record<string, unknown> = {}): DailyReviewPayload {
  return {
    date: "2026-10-29",
    title: "A股市场每日复盘 - 2026-10-29",
    market_summary: "指数震荡收涨，机器人主线领涨。",
    generated_at: "2026-10-29 16:10:00",
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
    sentiment_cycle: { stage: "主升共振" },
    previous_review_check: { checked_count: 4, hit_count: 3 },
    ...overrides,
  } as unknown as DailyReviewPayload;
}

function renderHero(review = makeReview(), checkAccuracy: number | null = 0.75) {
  render(
    <DailyReviewHero
      review={review}
      headline={buildReviewHeadline(review)}
      moodSummary="指数偏强，强势板块为机器人，弱势板块为白酒"
      checkAccuracy={checkAccuracy}
    />,
  );
}

describe("DailyReviewHero", () => {
  it("shows the conclusion, key metrics and stage on first screen", () => {
    renderHero();

    expect(screen.getByText(/指数震荡收涨/)).toBeInTheDocument();
    expect(screen.getByText("涨停家数")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("18.0%")).toBeInTheDocument();
    expect(screen.getByText("+0.85%")).toBeInTheDocument();
    expect(screen.getByText("主升共振")).toBeInTheDocument();
    expect(screen.getByText(/指数偏强/)).toBeInTheDocument();
  });

  it("surfaces the previous self-check accuracy", () => {
    renderHero();

    const check = screen.getByLabelText("昨日复盘自检命中率");
    expect(check).toHaveTextContent("75%");
    expect(check).toHaveTextContent("命中 3/4");
  });

  it("marks degraded quality and fallback generation", () => {
    renderHero(makeReview({ quality_status: "degraded", generation_status: "fallback" }));

    expect(screen.getByText("质量：降级")).toBeInTheDocument();
    expect(screen.getByText("报告：确定性兜底")).toBeInTheDocument();
  });

  it("hides the self-check ring when there is nothing to verify", () => {
    renderHero(makeReview({ previous_review_check: null }), null);

    expect(screen.queryByLabelText("昨日复盘自检命中率")).not.toBeInTheDocument();
  });
});
