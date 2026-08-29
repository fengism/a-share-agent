import { describe, expect, it } from "vitest";
import type { ChatStreamDelta } from "../../types/chat";
import {
  applyIndustryAgentEvent,
  createIndustryAgentProcessState,
} from "./agentProcess";

describe("industry chain agent process", () => {
  it("tracks plans, steps, and tool execution status", () => {
    const events: ChatStreamDelta[] = [
      {
        type: "plan",
        plan: {
          summary: "产业链证据计划",
          steps: [{
            id: "market",
            title: "市场边界",
            dependencies: [],
            status: "pending",
            attempt: 0,
          }],
        },
      },
      {
        type: "plan_step",
        plan_step: {
          step_id: "market",
          status: "running",
          detail: "正在调用 web_search",
          attempt: 1,
        },
      },
      {
        type: "tool_call",
        tool_call: {
          id: "call-1",
          type: "function",
          function: { name: "web_search", arguments: '{"query":"AI服务器"}' },
        },
      },
      {
        type: "tool_result",
        tool_result: {
          tool_call_id: "call-1",
          name: "web_search",
          content: '{"count":3}',
          is_error: false,
        },
      },
      {
        type: "plan_step",
        plan_step: {
          step_id: "market",
          status: "completed",
          detail: "已获取证据",
          attempt: 1,
        },
      },
      { type: "reasoning", content: "raw internal reasoning" },
      { type: "done" },
    ];

    const state = events.reduce(applyIndustryAgentEvent, createIndustryAgentProcessState());

    expect(state.status).toBe("Agent 调研完成");
    expect(state.plan?.steps[0]).toEqual(expect.objectContaining({
      status: "completed",
      detail: "已获取证据",
    }));
    expect(state.toolCalls[0]).toEqual(expect.objectContaining({
      name: "web_search",
      isExecuting: false,
      isError: false,
    }));
    expect(state.toolCalls[0]).not.toHaveProperty("result");
    expect(state).not.toHaveProperty("reasoningContent");
  });

  it("maps budget summaries to a skipped tool state", () => {
    const events: ChatStreamDelta[] = [
      {
        type: "tool_call",
        tool_call: {
          id: "call-budget",
          type: "function",
          function: { name: "web_search", arguments: "{}" },
        },
      },
      {
        type: "tool_result",
        tool_result: {
          tool_call_id: "call-budget",
          name: "web_search",
          content: "",
          is_error: false,
        },
        tool_result_summary: {
          status: "skipped",
          summary: "工具调用额度已用尽，已基于现有结果继续分析",
        },
      },
    ];
    const state = events.reduce(
      applyIndustryAgentEvent,
      createIndustryAgentProcessState(),
    );

    expect(state.toolCalls[0]).toEqual(expect.objectContaining({
      isExecuting: false,
      isError: false,
      isSkipped: true,
    }));
  });
});
