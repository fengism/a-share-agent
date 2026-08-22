import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ChatCapabilitiesResponse, ChatCapabilityAvailabilityResponse } from "../../../types/capabilities";
import { ChatCapabilityPresetBar } from "./ChatCapabilityPresetBar";

const capabilities: ChatCapabilitiesResponse = {
  skills: [
    {
      name: "stock_analysis",
      description: "个股分析",
      triggers: [],
      tool_names: ["analyze_stock"],
      rules: [],
      exclusions: [],
      priority: 30,
    },
    {
      name: "market_data",
      description: "市场数据",
      triggers: [],
      tool_names: ["get_market_data"],
      rules: [],
      exclusions: [],
      priority: 20,
    },
    {
      name: "url_content",
      description: "网页阅读",
      triggers: [],
      tool_names: ["fetch_url"],
      rules: [],
      exclusions: [],
      priority: 10,
    },
  ],
  agents: [
    {
      name: "technical",
      display_name: "技术面分析",
      description: "分析趋势",
      tool_names: ["get_stock_kline"],
      skill_names: ["stock_analysis"],
      max_rounds: 3,
    },
    {
      name: "news",
      display_name: "资讯分析",
      description: "分析资讯",
      tool_names: ["web_search"],
      skill_names: ["stock_analysis"],
      max_rounds: 3,
    },
  ],
  tools: [],
  unassigned_tools: [],
};

const availability: ChatCapabilityAvailabilityResponse = {
  llm: { status: "ready", reason: "配置完整" },
  skills: {
    stock_analysis: { status: "ready", reason: "可用" },
    market_data: { status: "unavailable", reason: "数据源未配置" },
    url_content: { status: "ready", reason: "可用" },
  },
  agents: {
    technical: { status: "ready", reason: "可用" },
    news: { status: "ready", reason: "可用" },
  },
};

describe("ChatCapabilityPresetBar", () => {
  it("applies presets using only account-available capabilities", () => {
    const onApply = vi.fn();
    render(
      <ChatCapabilityPresetBar
        capabilities={capabilities}
        availability={availability}
        disabledSkillNames={["url_content"]}
        disabledAgentNames={[]}
        skillNames={null}
        agentNames={null}
        onApply={onApply}
        disabled={false}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "快速分析" }));
    expect(onApply).toHaveBeenLastCalledWith(["stock_analysis"], ["technical"]);

    fireEvent.click(screen.getByRole("button", { name: "低成本" }));
    expect(onApply).toHaveBeenLastCalledWith(["stock_analysis"], []);
  });
});
