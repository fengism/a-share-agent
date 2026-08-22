import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ChatCapabilitiesResponse } from "../../types/capabilities";
import SkillAgentConfigCard from "./SkillAgentConfigCard";
import { applyCapabilityPreset, updateDisabledNames } from "./capabilityPreferences";

const capabilities: ChatCapabilitiesResponse = {
  skills: [
    {
      name: "stock_analysis",
      description: "个股分析",
      triggers: ["股票代码"],
      tool_names: ["analyze_stock"],
      rules: ["执行完整分析"],
      exclusions: [],
      priority: 30,
    },
    {
      name: "url_content",
      description: "网页阅读",
      triggers: ["网页链接"],
      tool_names: ["fetch_url"],
      rules: ["读取网页"],
      exclusions: [],
      priority: 10,
    },
  ],
  agents: [
    {
      name: "technical",
      display_name: "技术面分析",
      description: "分析趋势与技术指标",
      tool_names: ["get_stock_kline"],
      skill_names: ["stock_analysis"],
      max_rounds: 3,
    },
  ],
  tools: [],
  unassigned_tools: [],
};

describe("SkillAgentConfigCard", () => {
  it("shows the Skills owned by each Agent", () => {
    render(
      <SkillAgentConfigCard
        capabilities={capabilities}
        availability={undefined}
        disabledSkillNames={[]}
        disabledAgentNames={[]}
        isLoading={false}
        error={null}
        onRetry={vi.fn()}
        onChange={vi.fn()}
        onSave={vi.fn()}
        isSaving={false}
      />,
    );

    fireEvent.click(screen.getByText("Agent (1)"));

    expect(screen.getByText("关联 Skills")).toBeInTheDocument();
    expect(screen.getByText("stock_analysis")).toBeInTheDocument();
  });

  it("keeps disabled names in catalog order", () => {
    expect(
      updateDisabledNames(
        ["stock_analysis", "url_content", "macro_query"],
        ["macro_query", "unknown"],
        "url_content",
        false,
      ),
    ).toEqual(["url_content", "macro_query"]);
    expect(
      updateDisabledNames(
        ["stock_analysis", "url_content"],
        ["stock_analysis"],
        "stock_analysis",
        true,
      ),
    ).toEqual([]);
  });

  it("maps presets to disabled skill and agent lists", () => {
    expect(applyCapabilityPreset(
      "quick",
      ["stock_analysis", "stock_screening", "market_data", "url_content"],
      ["technical", "fundamental", "news"],
    )).toEqual({
      disabled_chat_skills: ["url_content"],
      disabled_chat_agents: ["news"],
    });

    expect(applyCapabilityPreset(
      "low_cost",
      ["stock_analysis", "url_content"],
      ["technical", "news"],
    )).toEqual({
      disabled_chat_skills: [],
      disabled_chat_agents: ["technical", "news"],
    });
  });

  it("emits skill and agent disabled-list patches", () => {
    const onChange = vi.fn();
    render(
      <SkillAgentConfigCard
        capabilities={capabilities}
        disabledSkillNames={[]}
        disabledAgentNames={[]}
        onChange={onChange}
        onSave={vi.fn()}
        isSaving={false}
      />,
    );

    fireEvent.click(screen.getByRole("switch", { name: "个股分析 Skill" }));
    expect(onChange).toHaveBeenLastCalledWith({ disabled_chat_skills: ["stock_analysis"] });

    fireEvent.click(screen.getByText("Agent (1)"));
    fireEvent.click(screen.getByRole("switch", { name: "技术面分析 Agent" }));
    expect(onChange).toHaveBeenLastCalledWith({ disabled_chat_agents: ["technical"] });
  });

  it("keeps its loading and error states local", () => {
    const { rerender } = render(
      <SkillAgentConfigCard
        disabledSkillNames={[]}
        disabledAgentNames={[]}
        onChange={vi.fn()}
        onSave={vi.fn()}
        isSaving={false}
        isLoading
      />,
    );

    expect(screen.getByLabelText("数据加载中")).toBeInTheDocument();

    rerender(
      <SkillAgentConfigCard
        disabledSkillNames={[]}
        disabledAgentNames={[]}
        onChange={vi.fn()}
        onSave={vi.fn()}
        isSaving={false}
        error={new Error("capabilities unavailable")}
      />,
    );
    expect(screen.getByText("capabilities unavailable")).toBeInTheDocument();
  });

  it("applies a capability preset and shows availability", () => {
    const onChange = vi.fn();
    render(
      <SkillAgentConfigCard
        capabilities={capabilities}
        availability={{
          llm: { status: "ready", reason: "配置完整" },
          skills: {
            stock_analysis: { status: "ready", reason: "可用" },
            url_content: { status: "degraded", reason: "部分能力受限" },
          },
          agents: {
            technical: { status: "ready", reason: "可用" },
          },
        }}
        disabledSkillNames={[]}
        disabledAgentNames={[]}
        onChange={onChange}
        onSave={vi.fn()}
        isSaving={false}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "低成本" }));
    expect(onChange).toHaveBeenLastCalledWith({
      disabled_chat_skills: [],
      disabled_chat_agents: ["technical"],
    });
    expect(screen.getByText("部分能力受限")).toBeInTheDocument();
  });
});
