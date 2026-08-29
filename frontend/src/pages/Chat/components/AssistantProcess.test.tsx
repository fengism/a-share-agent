import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AssistantProcess } from "./AssistantProcess";

describe("AssistantProcess", () => {
  it("renders the live agent plan and step statuses", () => {
    render(
      <AssistantProcess
        message={{
          id: "assistant-plan",
          role: "assistant",
          content: "",
          isStreaming: true,
          plan: {
            summary: "问题涉及技术面和风险评估",
            steps: [
              {
                id: "technical",
                title: "技术分析",
                description: "分析价格趋势",
                dependencies: [],
                status: "running",
                attempt: 1,
              },
              {
                id: "risk",
                title: "风险分析",
                description: "识别潜在风险",
                dependencies: ["technical"],
                status: "pending",
                attempt: 0,
              },
            ],
          },
        }}
      />,
    );

    expect(screen.getByText("问题涉及技术面和风险评估")).toBeInTheDocument();
    expect(screen.getByText("思路与计划")).toBeInTheDocument();
    expect(screen.getByText("技术分析")).toBeInTheDocument();
    expect(screen.getByText("执行中")).toBeInTheDocument();
    expect(screen.getByText("风险分析")).toBeInTheDocument();
    expect(screen.getByText("等待执行")).toBeInTheDocument();
  });

  it("does not expose raw model reasoning content", () => {
    render(
      <AssistantProcess
        message={{
          id: "assistant-reasoning",
          role: "assistant",
          content: "回答",
          isStreaming: false,
          reasoningContent: "private chain of thought",
          plan: {
            summary: "先核对行情，再评估风险",
            steps: [],
          },
        }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /已完成处理/ }));

    expect(screen.getByText("先核对行情，再评估风险")).toBeInTheDocument();
    expect(screen.queryByText("private chain of thought")).not.toBeInTheDocument();
  });

  it("shows only the actual tool name and arguments", () => {
    render(
      <AssistantProcess
        message={{
          id: "assistant-tool",
          role: "assistant",
          content: "",
          isStreaming: true,
          toolCalls: [{
            id: "call-1",
            name: "web_search",
            arguments: '{"query":"AI服务器"}',
            result: '{"count":3}',
            resultSummary: {
              summary: "返回 3 条记录",
              metadata: { source: "bing_cn" },
            },
            isExecuting: false,
          }],
        }}
      />,
    );

    expect(screen.getByText("网页搜索")).toBeInTheDocument();
    expect(screen.getByText("web_search")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /web_search/ }));

    expect(screen.getByText(/AI服务器/)).toBeInTheDocument();
    expect(screen.getByText("返回 3 条记录")).toBeInTheDocument();
    expect(screen.getByText("数据源：bing_cn")).toBeInTheDocument();
    expect(screen.queryByText(/"count": 3/)).not.toBeInTheDocument();
    expect(screen.queryByText("执行结果")).not.toBeInTheDocument();
  });

  it("labels degraded steps as data gaps", () => {
    render(
      <AssistantProcess
        message={{
          id: "assistant-gap",
          role: "assistant",
          content: "已按证据不足降级",
          isStreaming: false,
          plan: {
            summary: "核验公开资料",
            steps: [{
              id: "industry",
              title: "行业证据",
              dependencies: [],
              status: "degraded",
              detail: "正文抓取不足",
              attempt: 1,
            }],
          },
        }}
      />,
    );

    expect(screen.getByText("处理完成，存在数据缺口")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /处理完成，存在数据缺口/ }));
    expect(screen.getByText("数据缺口")).toBeInTheDocument();
  });

  it("renders exhausted tool budgets as skipped instead of failed", () => {
    render(
      <AssistantProcess
        message={{
          id: "assistant-budget",
          role: "assistant",
          content: "已基于现有资料完成回答",
          isStreaming: false,
          toolCalls: [{
            id: "call-budget",
            name: "web_search",
            arguments: "{}",
            resultSummary: {
              status: "skipped",
              summary: "工具调用额度已用尽，已基于现有结果继续分析",
            },
            isExecuting: false,
            isSkipped: true,
          }],
        }}
      />,
    );

    expect(screen.getByText("处理完成，存在数据缺口")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /处理完成，存在数据缺口/ }));
    expect(screen.getByText("已跳过")).toBeInTheDocument();
    expect(screen.queryByText("失败")).not.toBeInTheDocument();
  });
});
