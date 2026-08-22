import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AnalysisResult } from "../../types/stock";
import AIConclusion from "./AIConclusion";
import SentimentPanel from "./SentimentPanel";

vi.mock("../../api/queries", () => ({
  useCategorizedStockNews: () => ({
    data: {
      cls_news: [{ title: "财联社快讯", publish_time: "10:30" }],
      eastmoney_news: [{ title: "东方财富报道", source: "东方财富", publish_time: "09:45" }],
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useStockSentiment: () => ({
    data: { heat_score: 72, hot_rank: 15 },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useRetailSentiment: () => ({
    data: {
      score: 65,
      guba_post_count: 1,
      post_count: 1,
      bullish_ratio: 0.6,
      summary: "讨论情绪偏积极",
      sample_posts: [{ text: "看好后续表现", author: "投资者", publish_time: "10:00" }],
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

describe("analysis semantic lists", () => {
  it("renders sentiment samples and news as semantic lists", () => {
    render(<SentimentPanel code="600519" />);

    expect(screen.getAllByRole("list")).toHaveLength(3);
    expect(screen.getByText("看好后续表现")).toBeInTheDocument();
    expect(screen.getByText("财联社快讯")).toBeInTheDocument();
  });

  it("renders key factors and risks as semantic lists", () => {
    const result = {
      fundamental: { score: 8, summary: "基本面稳健" },
      technical: { score: 7, summary: "趋势向上" },
      sentiment: { score: 6, summary: "情绪平稳" },
      valuation_view: "合理",
      fair_value_range: [1450, 1650],
      overall_rating: 7.2,
      overall_summary: "综合表现稳健",
      estimated_price_range: [1500, 1700],
      signal: "buy",
      confidence: 0.8,
      key_factors: ["盈利能力稳定"],
      risk_warnings: ["估值波动风险"],
      current_price: 1520,
    } as unknown as AnalysisResult;

    render(<AIConclusion result={result} />);

    const lists = screen.getAllByRole("list");
    expect(lists).toHaveLength(2);
    expect(within(lists[0]).getByText("盈利能力稳定")).toBeInTheDocument();
    expect(within(lists[1]).getByText("估值波动风险")).toBeInTheDocument();
  });

  it("uses one clear conclusion hierarchy without duplicate teaser cards", () => {
    const result = {
      fundamental: { score: 8, summary: "基本面稳健" },
      technical: { score: 7, summary: "趋势向上" },
      sentiment: { score: 6, summary: "情绪平稳" },
      valuation_view: "合理",
      fair_value_range: [1450, 1650],
      overall_rating: 7.2,
      overall_summary: "综合表现稳健",
      estimated_price_range: [1500, 1700],
      signal: "buy",
      confidence: 0.8,
      key_factors: ["盈利能力稳定"],
      risk_warnings: ["估值波动风险"],
      current_price: 1520,
    } as unknown as AnalysisResult;

    render(<AIConclusion result={result} />);

    expect(screen.getByText("综合表现稳健")).toHaveClass("analysis-conclusion__summary");
    expect(screen.queryByText("投资要点")).not.toBeInTheDocument();
    expect(screen.queryByText("风险要点")).not.toBeInTheDocument();
    expect(screen.getByText("12个月估值区间")).toBeInTheDocument();
    expect(screen.getByText("当前价与预期空间")).toBeInTheDocument();
    expect(screen.getByText("决策因子")).toBeInTheDocument();
    expect(screen.getAllByRole("progressbar")).toHaveLength(4);
  });

});
