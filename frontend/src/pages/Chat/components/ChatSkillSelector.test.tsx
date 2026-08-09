import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ChatCapabilityAvailabilityResponse, SkillCapabilityInfo } from "../../../types/capabilities";
import { ChatSkillSelector } from "./ChatSkillSelector";

const skills: SkillCapabilityInfo[] = [
  {
    name: "market_data",
    description: "查询行情数据",
    triggers: ["行情"],
    tool_names: ["get_stock_quote"],
    rules: [],
    exclusions: [],
    priority: 10,
  },
  {
    name: "information_query",
    description: "查询公开资讯",
    triggers: ["资讯"],
    tool_names: ["web_search"],
    rules: [],
    exclusions: [],
    priority: 20,
  },
];

const availability: ChatCapabilityAvailabilityResponse = {
  llm: { status: "ready", reason: "配置完整" },
  skills: {
    market_data: { status: "ready", reason: "可用" },
    information_query: { status: "degraded", reason: "部分数据源受限" },
  },
  agents: {},
};

describe("ChatSkillSelector", () => {
  it("switches from account defaults to a session override", () => {
    const onChange = vi.fn();
    render(
      <ChatSkillSelector
        skills={skills}
        disabledSkillNames={[]}
        availability={availability}
        skillNames={null}
        onChange={onChange}
        disabled={false}
      />,
    );

    fireEvent.click(screen.getByText("自选 Skill"));

    expect(onChange).toHaveBeenCalledWith(["market_data", "information_query"]);
    expect(screen.getByText("部分数据源受限")).toBeInTheDocument();
  });

  it("excludes account-disabled skills from the override", () => {
    const onChange = vi.fn();
    render(
      <ChatSkillSelector
        skills={skills}
        disabledSkillNames={["information_query"]}
        availability={availability}
        skillNames={null}
        onChange={onChange}
        disabled={false}
      />,
    );

    fireEvent.click(screen.getByText("自选 Skill"));

    expect(onChange).toHaveBeenCalledWith(["market_data"]);
  });
});
