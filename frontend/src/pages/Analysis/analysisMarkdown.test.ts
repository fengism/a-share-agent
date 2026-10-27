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

  it("includes investment research framework sections when present", () => {
    const result: Partial<AnalysisResult> = {
      stock_code: "600519",
      stock_name: "贵州茅台",
      research_framework: {
        information_quality: { grade: "A", grade_rationale: "", limitations: [], evidence_confidence: 90, investment_certainty: 85, coverage_summary: "" },
        business_model: {
          economic_engine: "品牌定价权驱动超额利润",
          earnings_quality: "高现金流且极低坏账",
          revenue_drivers: [],
          segment_quality: [],
          operating_leverage: "",
          strengths: [],
          concerns: [],
        },
        moat: {
          overall_durability: "长久稳固",
          moats: [
            {
              moat_type: "brand_pricing",
              strength: "strong",
              direction: "stable",
              evidence: ["批价保持高端"],
              counterevidence: [],
              durability: "",
              threats: [],
              confidence: 0.9,
            },
          ],
          key_threats: [],
        },
        management: {
          track_record: "",
          capital_allocation: "",
          shareholder_alignment: "",
          succession_or_key_person_risk: "",
          strengths: [],
          concerns: [],
          confidence: null,
        },
        industry_position: {
          secular_context: "",
          value_chain_position: "",
          growth_drivers: [],
          competitive_position: "",
          technology_or_obsolescence_risk: "",
          concentration_risks: [],
          confidence: null,
        },
        inversion: {
          bear_case: "商务宴请消费严重滑坡导致渠道库存堰塞湖",
          risks: [
            {
              risk: "批价倒挂抛压",
              failure_path: "黄牛与经销商踩踏甩货",
              probability: "low",
              impact: "high",
              time_horizon: "1-2年",
              leading_indicators: ["整箱批价下跌破线"],
              mitigants: [],
              scenario: "bear",
            },
          ],
          bias_checks: [],
        },
        valuation: {
          method_summary: "",
          current_valuation: "",
          assumptions: [],
          scenarios: null,
          margin_of_safety: "",
          limitations: [],
        },
        actions: {
          new_investor_action: "watch",
          holder_action: "hold",
          rationale: "安全边际充足，但短期等待批价企稳",
          buy_or_add_range: [1400, 1500],
          add_triggers: [],
          sell_triggers: [],
          thesis_breakers: ["飞天批价跌破2000元且库存超过6个月"],
          monitoring_metrics: ["批价变化趋势", "经销商打款意愿"],
        },
        data_gaps: [],
      },
    };

    const md = buildAnalysisMarkdown(result as AnalysisResult);
    expect(md).toContain("## 六、商业模式与核心护城河");
    expect(md).toContain("品牌定价权驱动超额利润");
    expect(md).toContain("brand_pricing");
    expect(md).toContain("## 七、逆向思考与最强做空/下行逻辑 (Inversion)");
    expect(md).toContain("商务宴请消费严重滑坡导致渠道库存堰塞湖");
    expect(md).toContain("批价倒挂抛压");
    expect(md).toContain("## 八、条件化投资决策与失效跟踪");
    expect(md).toContain("飞天批价跌破2000元且库存超过6个月");
    expect(md).toContain("¥1400 - ¥1500");
  });
});
