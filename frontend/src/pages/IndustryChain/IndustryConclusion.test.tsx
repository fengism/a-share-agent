import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import IndustryConclusion from "./IndustryConclusion";
import type { IndustryChainResult } from "../../types/stock";

const baseResult: IndustryChainResult = {
  name: "AI 应用",
  summary: "AI 应用处于终端价值兑现环节。",
  positioning: "处于人工智能全产业链终端价值兑现环节",
  upstream: [],
  midstream: [],
  downstream: [],
  drivers: ["大模型算力成本下降"],
  risks: ["价值兑现不及预期"],
  key_stocks: [],
  llm_review: "",
  charts: [],
  evidence_catalog: [
    {
      evidence_id: "ev_1",
      tool_name: "web_fetch",
      title: "研报来源",
      source_urls: ["https://example.com/ai-report"],
    },
  ],
};

describe("IndustryConclusion", () => {
  it("renders short summary with Markdown support", () => {
    const result: IndustryChainResult = {
      ...baseResult,
      summary: "### 核心观点\n**算力是门槛**，应用是价值。详见（资料 1）。",
    };

    render(<IndustryConclusion result={result} />);

    const conclusion = screen.getByRole("region", { name: "产业链结论摘要" });
    expect(within(conclusion).getByRole("heading", { name: "核心观点" })).toBeInTheDocument();
    expect(within(conclusion).getByText("算力是门槛").tagName).toBe("STRONG");
    expect(within(conclusion).getByRole("link", { name: "资料 1" })).toHaveAttribute(
      "href",
      "https://example.com/ai-report",
    );
    // Short summary does not show expand button
    expect(screen.queryByText("展开完整研判正文")).not.toBeInTheDocument();
  });

  it("renders Markdown tables and bullet lists in summary", () => {
    const result: IndustryChainResult = {
      ...baseResult,
      summary: `## 结构化分层

- **基础设施层**：算力芯片与智算中心
- **应用层**：企业级 SaaS 与智能体

| 环节 | 代表厂商 |
| --- | --- |
| 上游 | 寒武纪 |
| 下游 | 金山办公 |`,
    };

    render(<IndustryConclusion result={result} />);

    const conclusion = screen.getByRole("region", { name: "产业链结论摘要" });
    expect(within(conclusion).getByRole("heading", { name: "结构化分层" })).toBeInTheDocument();
    expect(within(conclusion).getByRole("table")).toBeInTheDocument();
    expect(within(conclusion).getByText("寒武纪")).toBeInTheDocument();
    expect(within(conclusion).getByText("金山办公")).toBeInTheDocument();
  });

  it("shows expand/collapse toggle for long summary and toggles class", () => {
    const longSummary = `## 一、产业边界\n${"这是一段用于测试长文本研判摘要的详细内容。".repeat(15)}\n\n## 二、核心矛盾\n${"第二段长文本说明。".repeat(10)}`;
    const result: IndustryChainResult = {
      ...baseResult,
      summary: longSummary,
    };

    render(<IndustryConclusion result={result} />);

    const toggleBtn = screen.getByRole("button", { name: /展开完整研判正文/ });
    expect(toggleBtn).toBeInTheDocument();

    const summaryContent = document.querySelector(".industry-conclusion__summary-content");
    expect(summaryContent).toHaveClass("is-collapsed");

    // Click expand
    fireEvent.click(toggleBtn);
    expect(screen.getByRole("button", { name: /收起研判正文/ })).toBeInTheDocument();
    expect(summaryContent).toHaveClass("is-expanded");

    // Click collapse
    fireEvent.click(screen.getByRole("button", { name: /收起研判正文/ }));
    expect(screen.getByRole("button", { name: /展开完整研判正文/ })).toBeInTheDocument();
    expect(summaryContent).toHaveClass("is-collapsed");
  });
});
