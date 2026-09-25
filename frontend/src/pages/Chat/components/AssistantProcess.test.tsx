import { fireEvent, render, screen, within } from "@testing-library/react";
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

  it("shows provider-returned reasoning separately from the plan", () => {
    render(
      <AssistantProcess
        message={{
          id: "assistant-reasoning",
          role: "assistant",
          content: "回答",
          isStreaming: false,
          reasoningContent: "先核验公告，再比较财务指标",
          plan: {
            summary: "先核对行情，再评估风险",
            steps: [],
          },
        }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /已完成处理/ }));

    expect(screen.getByText("先核对行情，再评估风险")).toBeInTheDocument();
    expect(screen.getByText("先核验公告，再比较财务指标")).toBeInTheDocument();
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
  it("keeps public status history visible while answering and available after completion", () => {
    const message = {
      id: "process", role: "assistant" as const, content: "最终答案", isStreaming: true,
      processUpdates: [{ type: "status" as const, content: "正在核验一手资料" }],
    };
    const { rerender } = render(<AssistantProcess message={message} />);
    expect(screen.getByText("正在核验一手资料")).toBeInTheDocument();
    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "true");
    rerender(<AssistantProcess message={{ ...message, isStreaming: false }} />);
    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("正在核验一手资料")).toBeInTheDocument();
  });

  it("respects manual expansion and collapse across streaming updates and completion", () => {
    const message = {
      id: "manual", role: "assistant" as const, content: "", isStreaming: true,
      processUpdates: [{ type: "status" as const, content: "查找公开资料" }],
    };
    const { rerender } = render(<AssistantProcess message={message} />);
    fireEvent.click(screen.getByRole("button"));
    rerender(<AssistantProcess message={{ ...message, content: "回答增量" }} />);
    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(screen.getByRole("button"));
    rerender(<AssistantProcess message={{ ...message, isStreaming: false }} />);
    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "true");
  });

  it("renders structured research summaries and marks unfinished rounds without a spinner", () => {
    render(<AssistantProcess message={{
      id: "round", role: "assistant", content: "", isStreaming: false, processOutcome: "cancelled",
      processUpdates: [{ type: "round", round: {
        round_index: 1, round_total: 2, status: "running", objective: "核验公告",
        evidence_gaps: ["缺少原文"], tool_names: ["web_search"], tool_selection_reason: "查询一手资料",
        evidence_added: ["找到公告"], judgment_basis: ["来源为交易所"], conclusion: "需要进一步核验", next_step: "读取公告正文",
      } }],
    }} />);
    expect(screen.getByText("处理已停止")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button"));
    for (const text of ["第 1/2 轮调研", "已停止", "核验公告", "缺少原文", "查询一手资料", "找到公告", "来源为交易所", "需要进一步核验", "读取公告正文"]) {
      expect(screen.getByText(text)).toBeInTheDocument();
    }
    expect(screen.queryByLabelText("loading")).not.toBeInTheDocument();
  });

  it.each([ ["failed", "处理失败"], ["partial", "处理完成，存在数据缺口"], ["cancelled", "处理已停止"] ] as const)("shows %s even without plans/tools", (processOutcome, label) => {
    render(<AssistantProcess message={{ id: "outcome", role: "assistant", content: "", processOutcome }} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("does not invent a process for plain answers or blank reasoning", () => {
    const { container } = render(<AssistantProcess message={{ id: "plain", role: "assistant", content: "答案", reasoningContent: "  \n" }} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("streams reasoning without tools and makes it available in collapsed history", () => {
    const message = { id: "reasoning-only", role: "assistant" as const, content: "", isStreaming: true, reasoningContent: "先核验公告" };
    const { rerender } = render(<AssistantProcess message={message} />);
    expect(screen.getByText("模型正在推理")).toBeInTheDocument();
    expect(screen.getByText("先核验公告")).toBeInTheDocument();
    rerender(<AssistantProcess message={{ ...message, reasoningContent: "先核验公告，再比较指标" }} />);
    expect(screen.getByText("先核验公告，再比较指标")).toBeInTheDocument();
    rerender(<AssistantProcess message={{ ...message, isStreaming: false, processOutcome: "cancelled" }} />);
    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("先核验公告")).toBeInTheDocument();
    expect(screen.queryByLabelText("loading")).not.toBeInTheDocument();
  });

  it("renders model text literally without executing markup", () => {
    const reasoningContent = '<img src="https://example.com/track" onerror="alert(1)"><script>alert(1)</script>';
    const { container } = render(<AssistantProcess message={{ id: "literal", role: "assistant", content: "", isStreaming: true, reasoningContent }} />);
    expect(screen.getByText(reasoningContent)).toBeInTheDocument();
    expect(container.querySelector("img, script")).toBeNull();
  });

});

describe("AssistantProcess terminal rendering", () => {
  it.each(["cancelled", "failed"] as const)("settles stale child flags for a %s message", (processOutcome) => {
    const { container } = render(<AssistantProcess message={{
      id: "stale", role: "assistant", content: "已有内容", isStreaming: true, processOutcome,
      plan: { steps: [{ id: "step", title: "核验步骤", dependencies: [], status: "running", attempt: 1 }] },
      toolCalls: [
        { id: "done", name: "web_search", arguments: "{}", isExecuting: false, result: "公告证据" },
        { id: "live", name: "web_fetch", arguments: "{}", isExecuting: true },
      ],
      processUpdates: [{ type: "round", round: {
        round_index: 1, round_total: 1, status: "running", objective: "核验公告", evidence_gaps: [], tool_names: [],
        tool_selection_reason: "", evidence_added: ["已获得的证据"], judgment_basis: [], conclusion: "", next_step: "",
      } }],
    }} />);
    fireEvent.click(screen.getByRole("button", { name: /思考与执行过程/ }));
    expect(screen.getByText(processOutcome === "cancelled" ? "处理已停止" : "处理失败")).toBeInTheDocument();
    const liveTool = screen.getByRole("button", { name: /web_fetch/ });
    expect(within(liveTool).getByText(processOutcome === "cancelled" ? "已停止" : "失败")).toBeInTheDocument();
    expect(within(screen.getByRole("button", { name: /web_search/ })).getByText("已完成")).toBeInTheDocument();
    expect(screen.getByText("已获得的证据")).toBeInTheDocument();
    expect(screen.queryByText("执行中")).not.toBeInTheDocument();
    expect(screen.queryByText("调研中")).not.toBeInTheDocument();
    expect(container.querySelector('[aria-label="loading"]')).toBeNull();
  });

  it("does not render a stale historical tool as running or completed", () => {
    const { container } = render(<AssistantProcess message={{
      id: "legacy", role: "assistant", content: "", isStreaming: false,
      toolCalls: [{ id: "live", name: "web_fetch", arguments: "{}", isExecuting: true }],
    }} />);
    expect(screen.getByText("处理已停止")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /思考与执行过程/ }));
    expect(screen.getByText("已停止")).toBeInTheDocument();
    expect(screen.queryByText("已完成")).not.toBeInTheDocument();
    expect(container.querySelector('[aria-label="loading"]')).toBeNull();
  });
});
