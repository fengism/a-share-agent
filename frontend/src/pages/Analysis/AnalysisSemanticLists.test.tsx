import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { AnalysisResult } from "../../types/stock";
import AIConclusion from "./AIConclusion";

describe("analysis semantic lists", () => {
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
    expect(screen.queryByText("技术面")).not.toBeInTheDocument();
    expect(screen.queryByText("趋势向上")).not.toBeInTheDocument();
    expect(screen.queryByText("情绪面")).not.toBeInTheDocument();
    expect(screen.getAllByRole("progressbar")).toHaveLength(2);
  });

});
