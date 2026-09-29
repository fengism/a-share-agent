import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { AnalysisResult, InvestmentResearchFramework } from "../../types/stock";
import ResearchFrameworkPanel from "./ResearchFrameworkPanel";

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname}{location.search}{location.hash}</span>;
}

const researchFramework: InvestmentResearchFramework = {
  information_quality: {
    grade: "B",
    grade_rationale: "财务资料充分，管理层资料仍有限",
    evidence_confidence: 0.78,
    investment_certainty: 0.61,
    coverage_summary: "覆盖财务、估值、行业和主要风险",
    limitations: ["部分分部数据没有报告期"],
  },
  business_model: {
    economic_engine: "通过品牌溢价和稳定复购获得现金流",
    revenue_drivers: ["核心产品销量"],
    segment_quality: [{
      segment: "核心产品",
      role: "主要利润来源",
      growth_quality: "稳健",
      profitability_quality: "较高",
      recurrence: "较高",
      evidence_confidence: 0.8,
    }],
    earnings_quality: "经营现金流与利润方向一致",
    operating_leverage: "成本相对稳定",
    strengths: ["品牌认知稳定"],
    concerns: ["渠道库存需跟踪"],
  },
  moat: {
    moats: [{
      moat_type: "brand_pricing",
      evidence: ["核心产品价格稳定"],
      counterevidence: ["竞品持续扩张"],
      strength: "strong",
      direction: "stable",
      durability: "仍具持续性",
      threats: ["消费偏好迁移"],
      confidence: 0.75,
    }],
    overall_durability: "中长期仍需渠道数据验证",
    key_threats: ["需求结构变化"],
  },
  management: {
    track_record: "经营策略保持连贯",
    capital_allocation: "主业投入与分红并重",
    shareholder_alignment: "治理结构稳定",
    succession_or_key_person_risk: "接班安排需跟踪",
    strengths: [],
    concerns: [],
    confidence: 0.65,
  },
  industry_position: {
    secular_context: "行业进入存量竞争",
    value_chain_position: "品牌与渠道环节",
    growth_drivers: ["产品结构升级"],
    competitive_position: "头部位置",
    technology_or_obsolescence_risk: "较低",
    concentration_risks: ["单一品类占比较高"],
    confidence: 0.68,
  },
  inversion: {
    bear_case: "需求走弱与渠道去库存同时发生",
    risks: [{
      risk: "渠道库存",
      failure_path: "库存积压导致价格与回款承压",
      probability: "medium",
      impact: "high",
      time_horizon: "未来 4 个季度",
      leading_indicators: ["批价", "合同负债"],
      mitigants: ["渠道调节能力"],
      scenario: "bear",
    }],
    bias_checks: ["避免用历史高增长外推未来"],
  },
  valuation: {
    method_summary: "复用 PE、DCF 等现有估值结果",
    current_valuation: "估值处于合理区间",
    assumptions: ["利润保持稳定"],
    scenarios: {
      bull: { scenario: "bull", assumptions: ["需求恢复"], valuation_view: "偏低", fair_value_range: [1600, 1800], key_drivers: [], invalidating_conditions: ["需求未恢复"] },
      base: { scenario: "base", assumptions: ["稳健增长"], valuation_view: "合理", fair_value_range: [1450, 1650], key_drivers: [], invalidating_conditions: ["利润下滑"] },
      bear: { scenario: "bear", assumptions: ["需求承压"], valuation_view: "偏高", fair_value_range: null, key_drivers: [], invalidating_conditions: ["库存快速下降"] },
    },
    margin_of_safety: "等待价格回落或盈利上修",
    limitations: ["未独立计算反向 DCF"],
  },
  actions: {
    new_investor_action: "watch",
    holder_action: "hold",
    rationale: "当前赔率尚不突出",
    buy_or_add_range: [1400, 1480],
    add_triggers: ["估值进入安全边际"],
    sell_triggers: ["现金流持续弱于利润"],
    thesis_breakers: ["品牌定价权持续削弱"],
    monitoring_metrics: ["批价", "经营现金流"],
  },
  data_gaps: [{
    topic: "渠道库存",
    missing_data: "缺少统一口径",
    decision_impact: "影响需求判断",
    follow_up: "核对公告与渠道调研",
  }],
};

function analysisWithFramework(): AnalysisResult {
  return { stock_code: "600519", research_framework: researchFramework } as AnalysisResult;
}

describe("ResearchFrameworkPanel", () => {
  it("renders evidence confidence separately from investment certainty and exposes counterevidence", () => {
    render(<MemoryRouter><ResearchFrameworkPanel analysis={analysisWithFramework()} /></MemoryRouter>);

    expect(screen.getByText("B · 资料有限")).toBeInTheDocument();
    expect(screen.getByLabelText("证据可信度78%")).toBeInTheDocument();
    expect(screen.getByLabelText("投资确定性61%")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "生意与盈利引擎" })).toBeInTheDocument();
    expect(screen.getByText("竞品持续扩张")).toBeInTheDocument();
    expect(screen.getByText("库存积压导致价格与回款承压")).toBeInTheDocument();
    expect(screen.getByText("新投资者")).toBeInTheDocument();
    expect(screen.getByText("已持有者")).toBeInTheDocument();
    expect(screen.getByText("核对公告与渠道调研")).toBeInTheDocument();
    const gaps = screen.getByRole("heading", { name: "数据缺口与下一步核验" }).closest("section");
    expect(gaps).not.toBeNull();
    expect(within(gaps as HTMLElement).getByText("渠道库存")).toHaveClass("research-gap-list__topic");
    expect(within(gaps as HTMLElement).getByText("缺少统一口径")).toHaveClass("research-gap-list__description");
  });

  it("renders all three valuation scenarios and links to the valuation panel", () => {
    render(
      <MemoryRouter initialEntries={["/analysis/600519"]}>
        <ResearchFrameworkPanel analysis={analysisWithFramework()} />
        <LocationProbe />
      </MemoryRouter>,
    );

    const scenarios = screen.getByRole("heading", { name: "估值假设与三情景" }).closest("section");
    expect(scenarios).not.toBeNull();
    expect(within(scenarios as HTMLElement).getByText("乐观情景")).toBeInTheDocument();
    expect(within(scenarios as HTMLElement).getByText("基准情景")).toBeInTheDocument();
    expect(within(scenarios as HTMLElement).getByText("谨慎情景")).toBeInTheDocument();
    expect(within(scenarios as HTMLElement).getByText("证据不足，未给出区间")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /查看估值明细/ }));
    expect(screen.getByTestId("location")).toHaveTextContent("/stock/600519?tab=valuation#stock-details");
  });

  it("shows a structured DCF point estimate without claiming valuation evidence is absent", () => {
    const frameworkWithPointEstimate: InvestmentResearchFramework = {
      ...researchFramework,
      valuation: {
        ...researchFramework.valuation,
        scenarios: researchFramework.valuation.scenarios ? {
          ...researchFramework.valuation.scenarios,
          bull: {
            ...researchFramework.valuation.scenarios.bull,
            fair_value_range: null,
            valuation_view: "结构化DCF乐观情景每股价值1701.63元，仅为模型点估计。",
          },
        } : null,
      },
    };

    render(
      <MemoryRouter>
        <ResearchFrameworkPanel analysis={{ stock_code: "600519", research_framework: frameworkWithPointEstimate } as AnalysisResult} />
      </MemoryRouter>,
    );

    const scenarios = screen.getByRole("heading", { name: "估值假设与三情景" }).closest("section");
    expect(scenarios).not.toBeNull();
    expect(within(scenarios as HTMLElement).getByText("模型点估计 ¥1701.63")).toBeInTheDocument();
    expect(within(scenarios as HTMLElement).getByText("结构化DCF乐观情景每股价值1701.63元，仅为模型点估计。")).toBeInTheDocument();
  });

  it("uses an injected valuation action in a standalone workbench", () => {
    const onOpenValuation = vi.fn();
    render(
      <MemoryRouter initialEntries={["/investment-research/600519?date=20260807"]}>
        <ResearchFrameworkPanel analysis={analysisWithFramework()} onOpenValuation={onOpenValuation} />
        <LocationProbe />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: /查看估值明细/ }));
    expect(onOpenValuation).toHaveBeenCalledOnce();
    expect(screen.getByTestId("location")).toHaveTextContent("date=20260807");
    expect(screen.getByTestId("location")).not.toHaveTextContent("/stock/600519?tab=valuation#stock-details");
  });

  it("uses compact reading by default and allows switching to the complete report", () => {
    render(<MemoryRouter><ResearchFrameworkPanel analysis={analysisWithFramework()} /></MemoryRouter>);

    expect(screen.getByRole("navigation", { name: "研究结论章节导航" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "估值" })).toHaveAttribute("href", "#research-valuation");
    expect(screen.getByText("经营现金流与利润方向一致").closest(".research-section__content"))
      .toHaveAttribute("aria-hidden", "true");
    fireEvent.click(screen.getByText("完整报告"));
    expect(screen.getByText("经营现金流与利润方向一致").closest(".research-section__content"))
      .toHaveAttribute("aria-hidden", "false");
    fireEvent.click(screen.getByText("精简阅读"));
    expect(screen.getAllByText("通过品牌溢价和稳定复购获得现金流")[0]).toBeVisible();
    expect(screen.getByText("经营现金流与利润方向一致").closest(".research-section__content"))
      .toHaveAttribute("aria-hidden", "true");
  });

  it("forces a complete report during export", () => {
    render(
      <MemoryRouter>
        <ResearchFrameworkPanel analysis={analysisWithFramework()} forceFullReport />
      </MemoryRouter>,
    );

    expect(screen.getByText("经营现金流与利润方向一致").closest(".research-section__content"))
      .toHaveAttribute("aria-hidden", "false");
  });

  it("shows a truthful legacy state when no framework exists", () => {
    render(<MemoryRouter><ResearchFrameworkPanel analysis={{} as AnalysisResult} /></MemoryRouter>);

    expect(screen.getByText("该研究快照由旧版框架生成，暂无结构化研究结论")).toBeInTheDocument();
    expect(screen.queryByText("生意与盈利引擎")).not.toBeInTheDocument();
  });

  it("invites the user to run analysis before a result exists", () => {
    render(<MemoryRouter><ResearchFrameworkPanel analysis={null} /></MemoryRouter>);

    expect(screen.getByText("完成个股研究后查看结构化研究结论")).toBeInTheDocument();
    expect(screen.queryByText(/旧版框架/)).not.toBeInTheDocument();
  });
});
