import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import DailyReviewPosterModal from "./DailyReviewPosterModal";
import type { DailyReviewPayload, ReviewHeadline } from "./reviewView";

describe("DailyReviewPosterModal", () => {
  it("renders review summary and sentiment gauge inside poster modal", () => {
    const mockReview: DailyReviewPayload = {
      date: "2026-10-29",
      title: "指数放量主升主线共振",
      market_summary: "两市成交额放大至两万亿以上，主线板块全线领涨。",
      data_snapshot: {
        indices: [{ name: "上证指数", change_pct: 1.5 }],
        market_emotion: { up_count: 3600, down_count: 1200 },
        market_volume: { total_turnover: 21000 },
      } as unknown as DailyReviewPayload["data_snapshot"],
    };

    const mockHeadline: ReviewHeadline = {
      quality: "complete",
      generation: "ai",
      stage: "修复回暖",
      indexName: "上证指数",
      indexChangePct: 1.5,
      limitUpCount: 68,
      breakRate: 12.5,
      checkHit: 2,
      checkTotal: 3,
    };

    render(
      <DailyReviewPosterModal
        open={true}
        onClose={vi.fn()}
        review={mockReview}
        headline={mockHeadline}
        moodSummary="短线情绪亢奋，赚钱效应聚集"
      />,
    );

    expect(screen.getByText("生成复盘战报长图")).toBeInTheDocument();
    expect(screen.getByText("每日市场复盘战报")).toBeInTheDocument();
    expect(screen.getByText("指数放量主升主线共振")).toBeInTheDocument();
    expect(screen.getByText("两市成交额放大至两万亿以上，主线板块全线领涨。")).toBeInTheDocument();
    expect(screen.getByText("保存图片 (PNG)")).toBeInTheDocument();
    expect(screen.getByText("复制海报")).toBeInTheDocument();
  });
});
