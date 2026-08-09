import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import AgentProcessPanel from "./AgentProcessPanel";

describe("AgentProcessPanel", () => {
  it("renders the research plan and tool details", () => {
    render(
      <AgentProcessPanel
        plan={{
          summary: "产业链证据计划",
          steps: [{
            id: "market",
            title: "市场与产业边界",
            description: "搜索公开资料",
            dependencies: [],
            status: "running",
            attempt: 1,
          }],
        }}
        status="正在调用工具"
        toolCalls={[{
          id: "call-1",
          name: "web_search",
          arguments: '{"query":"AI服务器"}',
          result: '{"count":3}',
          isExecuting: false,
        }]}
        isRunning
      />,
    );

    expect(screen.getByText("Agent 执行过程")).toBeInTheDocument();
    expect(screen.getByText("市场与产业边界")).toBeInTheDocument();
    expect(screen.getByText("网页搜索")).toBeInTheDocument();

    fireEvent.click(screen.getByText("网页搜索"));

    expect(screen.getByText(/AI服务器/)).toBeInTheDocument();
    expect(screen.getByText(/"count": 3/)).toBeInTheDocument();
  });
});
