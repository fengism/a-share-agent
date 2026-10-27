import { describe, expect, it } from "vitest";
import type { IndustryChainResult } from "../../types/stock";
import { buildIndustryReportMarkdown } from "./industryReportMarkdown";

describe("buildIndustryReportMarkdown", () => {
  it("builds markdown from llm_review when available", () => {
    const result: Partial<IndustryChainResult> = {
      name: "光伏设备",
      llm_review: "## 产业综述\n\n光伏设备受益于全球清洁能源转型需求持续增长。",
    };
    const md = buildIndustryReportMarkdown(result as IndustryChainResult);
    expect(md).toContain("# 光伏设备 产业链投研报告");
    expect(md).toContain("光伏设备受益于全球清洁能源转型需求持续增长。");
  });

  it("avoids duplicate top-level title when llm_review already starts with h1", () => {
    const result: Partial<IndustryChainResult> = {
      name: "光伏设备",
      llm_review: "# 光伏设备产业链投研报告\n\n> 报告生成时间：2026-03-31\n\n## 1. 行业定位与核心结论\n\n行业持续景气。",
    };
    const md = buildIndustryReportMarkdown(result as IndustryChainResult);
    expect(md.match(/^# [^#]/gm)?.length).toBe(1);
    expect(md).toContain("# 光伏设备产业链投研报告");
  });

  it("builds structured markdown when llm_review is absent", () => {
    const result: Partial<IndustryChainResult> = {
      name: "半导体设备",
      summary: "半导体设备国产化替代进程加速。",
      research_theses: [
        { title: "先进制程突破", detail: "核心设备加速自研突破。" },
      ],
      key_stocks: [
        {
          name: "北方华创",
          code: "002371",
          role: "刻蚀与沉积设备龙头",
          benefit_path: "先进制程刻蚀机份额提升",
          realization_conditions: ["客户晶圆厂二期扩产招标顺利"],
        },
      ],
      upstream: [
        { name: "高纯石英材料", role: "设备反应腔耗材", companies: ["石英股份"], metric: "市占率 40%" },
      ],
      relationships: [
        {
          source_node: "高纯石英材料",
          target_node: "刻蚀与薄膜沉积设备",
          relation_type: "supply",
          title: "国产高纯石英良率提升，支撑刻蚀机出货",
          impact_direction: "positive",
          driver: "海外限供倒逼国产化",
          detail: "国产高纯石英良率提升，支撑刻蚀机出货",
          conditions: ["高纯砂纯度达标"],
        },
      ],
      risks: [
        "地缘政治摩擦与关键零部件出口管制风险。",
      ],
    };
    const md = buildIndustryReportMarkdown(result as IndustryChainResult);
    expect(md).toContain("# 半导体设备 产业链投研报告");
    expect(md).toContain("半导体设备国产化替代进程加速。");
    expect(md).toContain("### 1. 先进制程突破");
    expect(md).toContain("北方华创");
    expect(md).toContain("先进制程刻蚀机份额提升");
    expect(md).toContain("## 五、上下游环节与价值链分布");
    expect(md).toContain("高纯石英材料");
    expect(md).toContain("## 六、产业链传导机制与核心假设");
    expect(md).toContain("海外限供倒逼国产化");
    expect(md).toContain("## 十、潜在风险与跟踪提示");
  });

  it("renders BOM value distribution, cycle analysis and expectation divergences", () => {
    const result: Partial<IndustryChainResult> = {
      name: "人形机器人",
      summary: "人形机器人产业正处于量产前夜。",
      value_distribution: [
        {
          segment: "旋转执行器",
          cost_share: "25%",
          gross_margin_range: "45%~55%",
          profit_share: "高",
          pricing_power: "high",
          detail: "集成高精度减速器与伺服电机",
        },
      ],
      cycle_analysis: {
        stage: "概念验证向量产过渡期",
        capacity_utilization: "研发阶段开工率未饱和",
        expansion_lead_time: "核心零部件验证周期 12 个月",
        inflection_point: "预计 2026 年初出现规模化交付拐点",
        pass_through_ability: "中游本体集成商具备成本下移要求",
      },
      expectation_divergences: [
        {
          topic: "量产交付时间表",
          consensus: "市场预期 2025 年内实现万台交付",
          divergence: "受限于灵巧手传感器良率，规模交付可能延至 2026H1",
          catalyst_trigger: "关注 2025Q3 头部车厂实地测试定点公告",
        },
      ],
      key_stocks: [
        {
          name: "三花智控",
          code: "002050",
          role: "旋转与直线执行器总成",
          pe: "28.5",
          pe_percentile: "18.5% (近三年低估)",
          consensus_forecast: "24家机构预测 2025E EPS 1.85元",
          gross_margin: "31.2%",
          moat: "热管理量产制造与客户深度协同研发壁垒",
          eps_elasticity: "执行器单机价值 2 万元，出货 10 万台增厚净利约 3 亿元",
          price_change: "24.50 (+3.15%)",
          roe: "19.8%",
          growth_rate: "营收+18.2% / 净利+25.6%",
          restricted_risk: "近6个月预计解禁占流通盘 0.8%",
        },
      ],
    };
    const md = buildIndustryReportMarkdown(result as IndustryChainResult);
    expect(md).toContain("### 价值链 BOM 拆解与利润池分配");
    expect(md).toContain("旋转执行器");
    expect(md).toContain("45%~55%");
    expect(md).toContain("### 供需格局、周期定位与成本顺价机制");
    expect(md).toContain("概念验证向量产过渡期");
    expect(md).toContain("### 市场一致预期 vs 本次研究分歧（预期差推演）");
    expect(md).toContain("量产交付时间表");
    expect(md).toContain("PE: 28.5 [18.5% (近三年低估)]");
    expect(md).toContain("现价: 24.50 (+3.15%)");
    expect(md).toContain("**机构一致预期**：24家机构预测 2025E EPS 1.85元");
    expect(md).toContain("**毛利率**：31.2%");
    expect(md).toContain("**资本回报与成长**：ROE: 19.8% ｜ 业绩增速: 营收+18.2% / 净利+25.6%");
    expect(md).toContain("**限售解禁监控**：近6个月预计解禁占流通盘 0.8%");
    expect(md).toContain("热管理量产制造与客户深度协同研发壁垒");
  });
});
