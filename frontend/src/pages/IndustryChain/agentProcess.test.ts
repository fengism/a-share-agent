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

describe("industry chain research rounds", () => {
  it("groups tool calls and summaries by adaptive research round", () => {
    const events: ChatStreamDelta[] = [
      {
        type: "round_started",
        research_round: {
          round_index: 1,
          round_total: 4,
          status: "running",
          objective: "建立市场空间、竞争格局的完整证据基线",
          evidence_gaps: ["市场空间", "竞争格局"],
          tool_names: ["web_search"],
          tool_selection_reason: "覆盖首轮全部证据维度",
          evidence_added: [],
          judgment_basis: [],
          conclusion: "",
          next_step: "",
        },
      },
      {
        type: "tool_call",
        tool_call: {
          id: "round-1-call",
          type: "function",
          function: { name: "web_search", arguments: '{"query":"市场空间"}' },
        },
      },
      {
        type: "tool_result",
        tool_result: {
          tool_call_id: "round-1-call",
          name: "web_search",
          content: "",
          is_error: false,
        },
        tool_result_summary: { summary: "返回 3 条记录" },
      },
      {
        type: "round_completed",
        research_round: {
          round_index: 1,
          round_total: 4,
          status: "completed",
          objective: "建立市场空间、竞争格局的完整证据基线",
          evidence_gaps: ["竞争格局"],
          tool_names: ["web_search"],
          tool_selection_reason: "覆盖首轮全部证据维度",
          evidence_added: ["web_search：1 条"],
          judgment_basis: ["本轮新增 1 条有效工具证据"],
          conclusion: "首轮已确认市场空间",
          next_step: "下一轮聚焦补齐：竞争格局",
        },
      },
      {
        type: "round_started",
        research_round: {
          round_index: 2,
          round_total: 4,
          status: "running",
          objective: "补齐竞争格局的证据缺口",
          evidence_gaps: ["竞争格局"],
          tool_names: ["web_fetch"],
          tool_selection_reason: "仅选择可覆盖竞争格局的工具，避免重复首轮已完成的检索",
          evidence_added: [],
          judgment_basis: [],
          conclusion: "",
          next_step: "",
        },
      },
      {
        type: "tool_call",
        tool_call: {
          id: "round-2-call",
          type: "function",
          function: { name: "web_fetch", arguments: '{"url":"https://example.com"}' },
        },
      },
      {
        type: "round_completed",
        research_round: {
          round_index: 2,
          round_total: 4,
          status: "completed",
          objective: "补齐竞争格局的证据缺口",
          evidence_gaps: [],
          tool_names: ["web_fetch"],
          tool_selection_reason: "仅选择可覆盖竞争格局的工具，避免重复首轮已完成的检索",
          evidence_added: ["web_fetch：1 条"],
          judgment_basis: ["全部证据维度已满足"],
          conclusion: "已确认竞争格局",
          next_step: "证据维度已满足，结束自适应调研",
        },
      },
    ];

    const state = events.reduce(applyIndustryAgentEvent, createIndustryAgentProcessState());

    expect(state.rounds).toHaveLength(2);
    expect(state.rounds[0]).toEqual(expect.objectContaining({
      roundIndex: 1,
      status: "completed",
      conclusion: "首轮已确认市场空间",
    }));
    expect(state.rounds[0].toolCalls).toEqual([
      expect.objectContaining({ id: "round-1-call", isExecuting: false }),
    ]);
    expect(state.rounds[1]).toEqual(expect.objectContaining({
      roundIndex: 2,
      status: "completed",
      evidenceGaps: [],
    }));
    expect(state.rounds[1].toolCalls).toEqual([
      expect.objectContaining({ id: "round-2-call", isExecuting: true }),
    ]);
  });
});
