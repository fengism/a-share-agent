import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { IndustryChainOpportunity, IndustryChainResult } from "../../types/stock";
import IndustryOpportunityMap from "./IndustryOpportunityMap";
import IndustryReportChanges from "./IndustryReportChanges";
import IndustryDecisionResearch from "./IndustryDecisionResearch";
import IndustryEvidenceChecks from "./IndustryEvidenceChecks";
import { DEFAULT_INDUSTRY_SCOPE, industryScopeRequest } from "./industryScope";

const opportunity: IndustryChainOpportunity = {
  name: "示例公司", prosperity_score: 20, earnings_score: 20, valuation_score: 20,
  catalyst_score: 20, evidence_score: 20, risk_score: 0, total_score: 100,
};
const result: IndustryChainResult = {
  name: "示例", summary: "", upstream: [], midstream: [], downstream: [],
  drivers: [], risks: [], key_stocks: [{ name: "公司甲", business_relevance: "concept", benefit_path: "订单转收入", realization_conditions: ["订单交付"], invalidation_conditions: ["订单取消"], tracking_metrics: ["交付数量"] }],
  llm_review: "", charts: [],
};

describe("industry research quality", () => {
  it("hides legacy investment scores", () => {
    render(<IndustryOpportunityMap opportunities={[opportunity]} />);
    expect(screen.getByText("旧版评分已停用")).toBeInTheDocument();
    expect(screen.queryByText("100 分")).not.toBeInTheDocument();
    expect(screen.getByText("盈利、估值、景气：未评估")).toBeInTheDocument();
  });
  it("labels new score only as completeness", () => {
    render(<IndustryOpportunityMap opportunities={[{ ...opportunity, scoring_version: 2, score_kind: "research_completeness", completeness_score: 75 }]} />);
    expect(screen.getByText("资料完整度 75%")).toBeInTheDocument();
  });
  it("does not call incompatible scopes unchanged", () => {
    render(<IndustryReportChanges changes={{ previous_archive_id: "old", comparable: false, comparison_note: "区域不同", has_changes: false, added_count: 0, removed_count: 0, updated_count: 0, items: [] }} />);
    expect(screen.getByText("区域不同")).toBeInTheDocument();
    expect(screen.queryByText("核心信息与上一版一致")).not.toBeInTheDocument();
  });
  it("shows business conditions without assuming revenue", () => {
    render(<IndustryDecisionResearch result={result} />);
    expect(screen.getByText("概念布局")).toBeInTheDocument();
    expect(screen.getByText("未验证")).toBeInTheDocument();
    expect(screen.getByText("订单取消")).toBeInTheDocument();
  });
  it("shows unverified historical claims", () => {
    render(<IndustryEvidenceChecks result={result} />);
    fireEvent.click(screen.getByText("关键结论核验 · 原文匹配不等于事实核实"));
    expect(screen.getByText("待验证")).toBeInTheDocument();
  });
  it("passes selected refresh dimensions to request", () => {
    expect(industryScopeRequest({ ...DEFAULT_INDUSTRY_SCOPE, refresh_dimensions: ["events"] }).refresh_dimensions).toEqual(["events"]);
    expect(industryScopeRequest(DEFAULT_INDUSTRY_SCOPE)).not.toHaveProperty("refresh_dimensions");
  });
});

it("includes technology, chain and relation claims and filters unverified entries", () => {
  render(<IndustryEvidenceChecks result={{ ...result,
    upstream: [{ name: "原料环节" }],
    technology_routes: [{ title: "技术路线", verification_status: "quote_matched", citations: [{ evidence_id: "ev_batch", quote: "真实匹配片段", source_url: "https://example.com/second" }] }],
    relationships: [{ title: "供应关系", source_node: "原料", target_node: "客户", relation_type: "supply" }],
    evidence_catalog: [{ evidence_id: "ev_batch", tool_name: "fetch_urls", source_urls: ["https://example.com/first", "https://example.com/second"] }],
  }} />);
  fireEvent.click(screen.getByText("关键结论核验 · 原文匹配不等于事实核实"));
  expect(screen.getByText("原料环节")).toBeInTheDocument();
  expect(screen.getByText("供应关系")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "查看匹配原文" })).toHaveAttribute("href", "https://example.com/second");
  fireEvent.click(screen.getByLabelText("只看待验证"));
  expect(screen.queryByText("技术路线")).not.toBeInTheDocument();
  expect(screen.getByText("供应关系")).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("只看原文匹配"));
  expect(screen.getByText("技术路线")).toBeInTheDocument();
  expect(screen.queryByText("供应关系")).not.toBeInTheDocument();
});

it("never picks the first link of an ambiguous historical batch", () => {
  render(<IndustryEvidenceChecks result={{ ...result, key_stocks: [{ name: "公司甲", citations: [{ evidence_id: "ev_batch", quote: "引用正文", source_url: "javascript:alert(1)" }] }],
    evidence_catalog: [{ evidence_id: "ev_batch", tool_name: "fetch_urls", source_urls: ["https://example.com/first", "https://example.com/second"] }],
  }} />);
  fireEvent.click(screen.getByText("关键结论核验 · 原文匹配不等于事实核实"));
  expect(screen.getByText("原文链接未唯一定位")).toBeInTheDocument();
  expect(screen.queryByRole("link")).not.toBeInTheDocument();
});

it("separates forecast from inference without changing verification status", () => {
  render(<IndustryEvidenceChecks result={{ ...result, key_stocks: [],
    market_metrics: [{ label: "机构出货预测", value: "100万只", evidence_basis: "forecast", verification_status: "quote_matched" }],
    research_theses: [{ title: "有条件的盈利改善", claim_type: "inference", verification_status: "unverified" }],
    verification_repair: { status: "no_new_evidence", attempted_rounds: 1, note: "补证未取得新增正文" },
  }} />);
  fireEvent.click(screen.getByText("关键结论核验 · 原文匹配不等于事实核实"));
  expect(screen.getByText("补证未取得新增正文")).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("来源机构预测"));
  expect(screen.getByText("机构出货预测")).toBeInTheDocument();
  expect(screen.queryByText("有条件的盈利改善")).not.toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("研究推断"));
  expect(screen.getByText("有条件的盈利改善")).toBeInTheDocument();
  expect(screen.getByText("待验证")).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText("只看原文匹配"));
  expect(screen.getByText("当前筛选下没有结论")).toBeInTheDocument();
});

it("exposes operating transmission inputs, output metric, lag and failure conditions", () => {
  render(<IndustryDecisionResearch result={{ ...result, relationships: [{ title: "终端动销到补库", source_node: "终端渠道", target_node: "生产厂商", relation_type: "transmission", driver: "渠道库存下降且动销改善", target_metric: "厂商新增订单", detail: "补库意愿取决于真实销售而不是压货", tracking_metrics: ["渠道库存月数", "销售回款"], conditions: ["库存正常化"], invalidation: "库存再次积压" }] }} />);
  expect(screen.getByText("终端渠道 → 生产厂商")).toBeInTheDocument();
  expect(screen.getByText("渠道库存下降且动销改善")).toBeInTheDocument();
  expect(screen.getByText("厂商新增订单")).toBeInTheDocument();
  expect(screen.getByText("未知，不假设即时兑现")).toBeInTheDocument();
  expect(screen.getByText("渠道库存月数；销售回款")).toBeInTheDocument();
});
