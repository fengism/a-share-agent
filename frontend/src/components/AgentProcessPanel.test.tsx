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
    expect(screen.getByText("web_search")).toBeInTheDocument();
    expect(screen.queryByText("网页搜索")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("web_search"));

    expect(screen.getByText(/AI服务器/)).toBeInTheDocument();
    expect(screen.queryByText(/"count": 3/)).not.toBeInTheDocument();
    expect(screen.queryByText("执行结果")).not.toBeInTheDocument();
  });

  it("shows cancelled tools as stopped", () => {
    render(
      <AgentProcessPanel
        status=""
        toolCalls={[{
          id: "call-2",
          name: "fetch_url",
          arguments: "{}",
          isExecuting: false,
          isCancelled: true,
        }]}
        isRunning={false}
      />,
    );

    expect(screen.getAllByText("已停止")).toHaveLength(2);
  });
});
