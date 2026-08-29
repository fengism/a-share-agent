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
          resultSummary: {
            summary: "返回 3 条记录",
            sources: [{ title: "公司公告", url: "https://example.com/report", domain: "example.com" }],
          },
          isExecuting: false,
        }]}
        isRunning
      />,
    );

    expect(screen.getByText("Agent 思考与执行")).toBeInTheDocument();
    expect(screen.getByText("0/1 个步骤 · 1 次工具调用")).toBeInTheDocument();
    expect(screen.getByText("思路摘要")).toBeInTheDocument();
    expect(screen.getByText("产业链证据计划")).toBeInTheDocument();
    expect(screen.getByText("市场与产业边界")).toBeInTheDocument();
    expect(screen.getByText("网页搜索")).toBeInTheDocument();
    expect(screen.getByText("web_search")).toBeInTheDocument();

    fireEvent.click(screen.getByText("网页搜索"));

    expect(screen.getByText(/AI服务器/)).toBeInTheDocument();
    expect(screen.getByText("返回 3 条记录")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /公司公告/ })).toHaveAttribute(
      "href",
      "https://example.com/report",
    );
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

    expect(screen.getByText("已停止")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Agent 思考与执行/ }));
    expect(screen.getAllByText("已停止")).toHaveLength(2);
  });

  it("shows degraded evidence as a data gap instead of a failure", () => {
    render(
      <AgentProcessPanel
        plan={{
          summary: "证据不足时降级",
          steps: [{
            id: "moat",
            title: "护城河证据",
            dependencies: [],
            status: "degraded",
            detail: "正文证据不足",
            attempt: 1,
          }],
        }}
        status="Agent 调研完成"
        toolCalls={[]}
        isRunning={false}
      />,
    );

    expect(screen.getByText("数据缺口")).toBeInTheDocument();
    expect(screen.queryByText("执行失败")).not.toBeInTheDocument();
  });

  it("groups repeated tool calls and summarizes failures", () => {
    render(
      <AgentProcessPanel
        status="Agent 调研完成"
        toolCalls={[
          {
            id: "call-1",
            name: "web_search",
            arguments: '{"query":"行业规模"}',
            isExecuting: false,
          },
          {
            id: "call-2",
            name: "web_search",
            arguments: '{"query":"竞争格局"}',
            isExecuting: false,
            isError: true,
          },
        ]}
        isRunning={false}
      />,
    );

    expect(screen.getByText("2 次工具调用")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Agent 思考与执行/ }));
    expect(screen.getAllByText("网页搜索")).toHaveLength(1);
    expect(screen.getByText("1/2 失败")).toBeInTheDocument();
  });

  it("shows budget exhaustion as a skipped data gap", () => {
    render(
      <AgentProcessPanel
        status="Agent 调研完成"
        toolCalls={[{
          id: "call-budget",
          name: "web_search",
          arguments: "{}",
          resultSummary: {
            status: "skipped",
            summary: "工具调用额度已用尽，已基于现有结果继续分析",
          },
          isExecuting: false,
          isSkipped: true,
        }]}
        isRunning={false}
      />,
    );

    expect(screen.getByText("数据缺口")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Agent 思考与执行/ }));
    expect(screen.getByText("已跳过")).toBeInTheDocument();
    expect(screen.getByText("工具调用额度已用尽，已基于现有结果继续分析")).toBeInTheDocument();
    expect(screen.queryByText(/tool_budget_exceeded/)).not.toBeInTheDocument();
  });
});
