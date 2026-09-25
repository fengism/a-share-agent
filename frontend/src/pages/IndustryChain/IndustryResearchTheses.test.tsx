import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import IndustryResearchTheses from "./IndustryResearchTheses";
import type { IndustryChainResult } from "../../types/stock";

const result: IndustryChainResult = { name: "测试", summary: "", upstream: [], midstream: [], downstream: [], drivers: [], risks: [], key_stocks: [], llm_review: "", charts: [] };
it("keeps historical archives readable without inventing depth", () => {
  const { container } = render(<IndustryResearchTheses result={result} />);
  expect(container).toBeEmptyDOMElement();
});
it("shows the mechanism, conditions and falsification without declaring proof", () => {
  render(<IndustryResearchTheses result={{ ...result, research_theses: [{ title: "需求到利润", detail: "需求改善不等于现金流改善", mechanism: "订单→交付→收入→回款", conditions: ["验收完成"], invalidation: "应收账款持续上升", tracking_metrics: ["现金回款"], verification_status: "quote_matched" }] }} />);
  expect(screen.getByText("订单→交付→收入→回款")).toBeInTheDocument();
  expect(screen.getByText("应收账款持续上升")).toBeInTheDocument();
  expect(screen.getByText("本次未取得反向证据")).toBeInTheDocument();
  expect(screen.getByText("前提原文已匹配 · 推导待复核")).toBeInTheDocument();
});

it("shows downstream-driven chain path instead of a generic mechanism alone", () => {
  render(<IndustryResearchTheses result={{ ...result, research_theses: [{ title: "需求传导", chain_path: ["终端客户", "整机生产", "核心零部件"], mechanism: "客户采购形成整机订单，进而形成零部件需求", verification_notes: ["部分传导边的事实前提未匹配原文，路径仅为待验证假设。"] }] }} />);
  expect(screen.getByText("终端客户 → 整机生产 → 核心零部件")).toBeInTheDocument();
  expect(screen.getByText("部分传导边的事实前提未匹配原文，路径仅为待验证假设。")).toBeInTheDocument();
  expect(screen.getByText("前提证据不足 · 待验证")).toBeInTheDocument();
});
