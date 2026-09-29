import { describe, expect, it } from "vitest";
import type { AnalysisResult } from "../../types/stock";
import { buildAnalysisMarkdown } from "./analysisMarkdown";

describe("buildAnalysisMarkdown", () => {
  it("generates markdown document from analysis result", () => {
    const result: Partial<AnalysisResult> = {
      stock_code: "600519",
      stock_name: "贵州茅台",
      analysis_date: "2026-08-25",
      current_price: 1520.5,
      overall_rating: 8.5,
      signal: "buy",
      confidence: 0.85,
      overall_summary: "白酒龙头，护城河极深，估值处于历史中枢偏下。",
      key_factors: ["高端白酒需求韧性强", "直销比例提升优化利润率"],
      risk_warnings: ["消费复苏不及预期"],
      fair_value_range: [1600, 1800],
      estimated_price_range: [1700, 1900],
      valuation_view: "当前PE处于相对合理区间",
      technical: {
        score: 7,
        support_level: 1480,
        resistance_level: 1600,
        trend: "震荡筑底",
        summary: "缩量回踩年线后企稳",
        strengths: ["站稳年线"],
        risks: ["量能偏弱"],
      },
    };

    const md = buildAnalysisMarkdown(result as AnalysisResult);
    expect(md).toContain("# 贵州茅台 (600519) 深度投研分析报告");
    expect(md).toContain("> 分析日期：2026-08-25");
    expect(md).toContain("> 最新价格：¥1520.50");
    expect(md).toContain("**综合评分**：8.5 / 10");
    expect(md).toContain("**置信度**：85%");
    expect(md).toContain("白酒龙头，护城河极深");
    expect(md).toContain("1. 高端白酒需求韧性强");
    expect(md).toContain("1. 消费复苏不及预期");
    expect(md).toContain("公允价值区间**：¥1600 - ¥1800");
    expect(md).toContain("支撑位**：¥1480");
  });
});
