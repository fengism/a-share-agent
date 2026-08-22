import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AgentCapabilityInfo, ChatCapabilityAvailabilityResponse } from "../../../types/capabilities";
import { ChatAgentSelector } from "./ChatAgentSelector";

const agents: AgentCapabilityInfo[] = [
  {
    name: "technical",
    display_name: "技术面分析",
    description: "分析趋势",
    tool_names: ["get_stock_kline"],
    skill_names: ["stock_analysis"],
    max_rounds: 3,
  },
  {
    name: "risk",
    display_name: "风险评估",
    description: "分析风险",
    tool_names: ["get_stock_risk_data"],
    skill_names: ["stock_analysis"],
    max_rounds: 3,
  },
];

const availability: ChatCapabilityAvailabilityResponse = {
  llm: { status: "ready", reason: "配置完整" },
  skills: {},
  agents: {
    technical: { status: "ready", reason: "可用" },
    risk: { status: "degraded", reason: "部分工具受限" },
  },
};

describe("ChatAgentSelector", () => {
  it("switches from automatic routing to a session override", () => {
    const onChange = vi.fn();
    render(
      <ChatAgentSelector
        agents={agents}
        disabledAgentNames={[]}
        availability={availability}
        agentNames={null}
        onChange={onChange}
        disabled={false}
      />,
    );

    fireEvent.click(screen.getByText("自选 Agent"));

    expect(onChange).toHaveBeenCalledWith(["technical", "risk"]);
    expect(screen.getByText("部分工具受限")).toBeInTheDocument();
  });

  it("excludes account-disabled agents from the override", () => {
    const onChange = vi.fn();
    render(
      <ChatAgentSelector
        agents={agents}
        disabledAgentNames={["risk"]}
        availability={availability}
        agentNames={null}
        onChange={onChange}
        disabled={false}
      />,
    );

    fireEvent.click(screen.getByText("自选 Agent"));

    expect(onChange).toHaveBeenCalledWith(["technical"]);
  });
});
