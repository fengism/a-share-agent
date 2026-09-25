import { beforeEach, describe, expect, it, vi } from "vitest";
import type { AgentResearchRound } from "../../types/chat";
import type { ChatStreamCallbacks } from "../../api/chat";
import { useChatStore } from "../../store/chatStore";
import { setActiveUserScope } from "../../store/userScope";
import { startChatRuntime, stopChatRuntime } from "./chatRuntime";

const { streamChat } = vi.hoisted(() => ({ streamChat: vi.fn() }));
vi.mock("../../api/chat", () => ({ streamChat }));

describe("chatRuntime", () => {
  beforeEach(() => {
    stopChatRuntime();
    setActiveUserScope(null);
    setActiveUserScope(1);
    streamChat.mockReset();
  });

  it("keeps the stream outside a page component and finalizes on global stop", () => {
    const controller = new AbortController();
    const abort = vi.spyOn(controller, "abort");
    streamChat.mockReturnValue(controller);
    expect(startChatRuntime({ input: "分析贵州茅台", history: [] })).toBe(true);
    expect(useChatStore.getState().isStreaming).toBe(true);
    expect(useChatStore.getState().activeRunLabel).toBe("分析贵州茅台");

    expect(stopChatRuntime()).toBe(true);
    expect(abort).toHaveBeenCalledOnce();
    expect(useChatStore.getState().isStreaming).toBe(false);
    const messages = useChatStore.getState().messages;
    expect(messages[messages.length - 1]?.isStreaming).toBe(false);
    expect(messages[messages.length - 1]?.processOutcome).toBe("cancelled");
  });

  it("keeps receiving deltas after the caller that started it is gone", () => {
    let callbacks: ChatStreamCallbacks | undefined;
    streamChat.mockImplementation((_input, _history, handlers) => {
      callbacks = handlers;
      return new AbortController();
    });

    expect(startChatRuntime({ input: "第一次", history: [] })).toBe(true);
    callbacks?.onDelta({ type: "text", content: "后台完成" });
    callbacks?.onDone();

    const messages = useChatStore.getState().messages;
    expect(messages[messages.length - 1]?.content).toBe("后台完成");
    expect(messages[messages.length - 1]?.isStreaming).toBe(false);
    expect(useChatStore.getState().isStreaming).toBe(false);
  });

  it("ignores a second start while another chat run is active", () => {
    streamChat.mockReturnValue(new AbortController());

    expect(startChatRuntime({ input: "第一次", history: [] })).toBe(true);
    expect(startChatRuntime({ input: "第二次", history: [] })).toBe(false);
    expect(streamChat).toHaveBeenCalledOnce();
  });
  it("records streamed status and research summaries, preserving partial completion", () => {
    let callbacks: ChatStreamCallbacks | undefined;
    streamChat.mockImplementation((_input, _history, handlers) => {
      callbacks = handlers;
      return new AbortController();
    });
    startChatRuntime({ input: "检查公告", history: [] });
    callbacks!.onDelta({ type: "status", content: "核对公告" });
    callbacks!.onDelta({ type: "status", content: "核对公告" });
    const round = { round_index: 1, round_total: 1, status: "running" as const, objective: "读取公告", evidence_gaps: [], tool_names: [], tool_selection_reason: "查阅一手资料", evidence_added: [], judgment_basis: [], conclusion: "", next_step: "" };
    callbacks!.onDelta({ type: "round_started", research_round: round });
    callbacks!.onDelta({ type: "text", content: "已有结论" });
    callbacks!.onDelta({ type: "round_completed", research_round: { ...round, status: "degraded", conclusion: "资料不足" } });
    callbacks!.onDelta({ type: "done", status: "partial", warnings: ["资料不足"] });
    callbacks!.onDone();
    const message = useChatStore.getState().messages[useChatStore.getState().messages.length - 1]!;
    expect(message.processUpdates).toEqual([
      { type: "status", content: "核对公告" },
      { type: "round", round: { ...round, status: "degraded", conclusion: "资料不足" } },
    ]);
    expect(message.content).toContain("已有结论");
    expect(message.processOutcome).toBe("partial");
    expect(message.isStreaming).toBe(false);
  });

  it("keeps other agents running after a plan step fails, then preserves partial completion", () => {
    let callbacks: ChatStreamCallbacks | undefined;
    streamChat.mockImplementation((_input, _history, handlers) => {
      callbacks = handlers;
      return new AbortController();
    });
    startChatRuntime({ input: "多维分析", history: [] });
    callbacks!.onDelta({
      type: "plan",
      plan: {
        steps: [
          { id: "news", title: "新闻分析", status: "running", dependencies: [], attempt: 1 },
          { id: "fundamental", title: "基本面分析", status: "running", dependencies: [], attempt: 1 },
        ],
      },
    });
    callbacks!.onDelta({
      type: "plan_step",
      plan_step: { step_id: "news", status: "failed", detail: "新闻源暂不可用", attempt: 1 },
    });
    expect(useChatStore.getState().isStreaming).toBe(true);
    const running = useChatStore.getState().messages.slice(-1)[0]!;
    expect(running.isStreaming).toBe(true);
    expect(running.processOutcome).toBeUndefined();
    expect(running.plan?.steps[1].status).toBe("running");

    callbacks!.onDelta({
      type: "plan_step",
      plan_step: { step_id: "fundamental", status: "completed", attempt: 1 },
    });
    callbacks!.onDelta({ type: "text", content: "基于基本面形成综合结论" });
    callbacks!.onDelta({ type: "done", status: "partial", warnings: ["新闻分析未完成"] });
    const state = useChatStore.getState();
    const message = state.messages.slice(-1)[0]!;
    expect(state.isStreaming).toBe(false);
    expect(message.processOutcome).toBe("partial");
    expect(message.content).toContain("基于基本面形成综合结论");
    expect(message.plan?.steps.map((step) => step.status)).toEqual(["failed", "completed"]);
  });

  it.each(["event", "connection"])("retains failed status for a %s error", (source) => {
    let callbacks: ChatStreamCallbacks | undefined;
    streamChat.mockImplementation((_input, _history, handlers) => {
      callbacks = handlers;
      return new AbortController();
    });
    startChatRuntime({ input: "核验", history: [] });
    callbacks!.onDelta({ type: "status", content: "正在核验" });
    if (source === "event") {
      callbacks!.onDelta({ type: "error", error: "服务暂不可用" });
      callbacks!.onDone();
    } else callbacks!.onError(new Error("连接中断"));
    const message = useChatStore.getState().messages[useChatStore.getState().messages.length - 1]!;
    expect(message.processOutcome).toBe("failed");
    expect(message.processUpdates).toEqual([{ type: "status", content: "正在核验" }]);
    expect(message.isStreaming).toBe(false);
  });

  it("keeps all reasoning turns when done contains only the final turn snapshot", () => {
    let callbacks: ChatStreamCallbacks | undefined;
    streamChat.mockImplementation((_input, _history, handlers) => {
      callbacks = handlers;
      return new AbortController();
    });
    startChatRuntime({ input: "核验", history: [] });
    callbacks!.onDelta({ type: "reasoning", content: "先核验公告。" });
    callbacks!.onDelta({ type: "reasoning", content: "再比较指标。" });
    callbacks!.onDelta({ type: "text", content: "最终答案" });
    callbacks!.onDelta({ type: "done", reasoning_content: "再比较指标。" });
    callbacks!.onDone();
    const state = useChatStore.getState();
    const message = state.messages[state.messages.length - 1]!;
    expect(message.reasoningContent).toBe("先核验公告。再比较指标。");
    expect(message.content).toBe("最终答案");
    expect(message.isStreaming).toBe(false);
    expect(JSON.stringify(state.history)).not.toContain("先核验公告");
  });

  it("uses the done snapshot when reasoning deltas are absent", () => {
    let callbacks: ChatStreamCallbacks | undefined;
    streamChat.mockImplementation((_input, _history, handlers) => {
      callbacks = handlers;
      return new AbortController();
    });
    startChatRuntime({ input: "核验", history: [] });
    callbacks!.onDelta({ type: "done", reasoning_content: "模型返回的完整推理" });
    callbacks!.onDone();
    const messages = useChatStore.getState().messages;
    expect(messages[messages.length - 1]!.reasoningContent).toBe("模型返回的完整推理");
  });

  it("flushes reasoning on stop and ignores late deltas", () => {
    let callbacks: ChatStreamCallbacks | undefined;
    streamChat.mockImplementation((_input, _history, handlers) => {
      callbacks = handlers;
      return new AbortController();
    });
    startChatRuntime({ input: "核验", history: [] });
    callbacks!.onDelta({ type: "reasoning", content: "已返回的推理" });
    stopChatRuntime();
    callbacks!.onDelta({ type: "reasoning", content: "迟到内容" });
    callbacks!.onDelta({ type: "done", reasoning_content: "迟到快照" });
    callbacks!.onDone();
    const messages = useChatStore.getState().messages;
    const message = messages[messages.length - 1]!;
    expect(message.reasoningContent).toBe("已返回的推理");
    expect(message.processOutcome).toBe("cancelled");
    expect(message.isStreaming).toBe(false);
  });

  it("preserves source boundaries across frames and retries without duplicating text", () => {
    let callbacks: ChatStreamCallbacks | undefined;
    streamChat.mockImplementation((_input, _history, handlers) => {
      callbacks = handlers;
      return new AbortController();
    });
    startChatRuntime({ input: "核验", history: [] });
    const source = { block_id: "first", source: "财务", stage: "agent" as const, turn: 1, attempt: 1 };
    callbacks!.onDelta({ type: "reasoning", content: "先", reasoning_source: source });
    callbacks!.onDelta({ type: "status", content: "处理中" });
    callbacks!.onDelta({ type: "reasoning", content: "核验", reasoning_source: source });
    callbacks!.onDelta({ type: "reasoning", content: "再分析", reasoning_source: { ...source, block_id: "retry", turn: 2, attempt: 2 } });
    callbacks!.onDelta({ type: "done", reasoning_content: "再分析" });
    callbacks!.onDone();
    const messages = useChatStore.getState().messages;
    const message = messages[messages.length - 1]!;
    expect(message.reasoningContent).toBe("先核验再分析");
    expect(message.reasoningBlocks).toEqual([
      { ...source, start: 0, end: 3 },
      { ...source, block_id: "retry", turn: 2, attempt: 2, start: 3, end: 6 },
    ]);
    expect(JSON.stringify(useChatStore.getState().history)).not.toContain("先核验");
  });

});

describe("chatRuntime terminal state synchronization", () => {
  let callbacks: ChatStreamCallbacks;
  let controller: AbortController;
  const round: AgentResearchRound = {
    round_index: 1, round_total: 2, status: "running", objective: "核验证据", evidence_gaps: [],
    tool_names: ["web_fetch"], tool_selection_reason: "读取原文", evidence_added: ["已找到公告"],
    judgment_basis: [], conclusion: "", next_step: "",
  };
  const currentMessage = () => useChatStore.getState().messages.slice(-1)[0]!;
  beforeEach(() => {
    stopChatRuntime();
    setActiveUserScope(null);
    setActiveUserScope(1);
    streamChat.mockReset();
    streamChat.mockImplementation((_input, _history, handlers) => {
      callbacks = handlers;
      controller = new AbortController();
      return controller;
    });
    startChatRuntime({ input: "核验", history: [] });
    callbacks.onDelta({ type: "plan", plan: { steps: [
      { id: "verify", title: "核验", status: "running", attempt: 1, dependencies: [] },
    ] } });
    callbacks.onDelta({ type: "round_started", research_round: round });
    callbacks.onDelta({ type: "tool_call", tool_call: { id: "tool", type: "function", function: { name: "web_fetch", arguments: "{}" } } });
    callbacks.onDelta({ type: "reasoning", content: "已经收到的推理" });
    callbacks.onDelta({ type: "text", content: "已生成内容" });
  });

  it("stops plan, round, tools and buffered text even if abort synchronously calls back", () => {
    controller.signal.addEventListener("abort", () => {
      callbacks.onDelta({ type: "tool_result", tool_result: { tool_call_id: "tool", name: "web_fetch", content: "迟到结果", is_error: false } });
      callbacks.onDelta({ type: "done", status: "completed" });
      callbacks.onDone();
    });
    expect(stopChatRuntime()).toBe(true);
    expect(currentMessage()).toMatchObject({
      isStreaming: false, processOutcome: "cancelled", content: "已生成内容", reasoningContent: "已经收到的推理",
      plan: { steps: [{ status: "cancelled" }] },
      processUpdates: [{ round: { status: "cancelled", evidence_added: ["已找到公告"] } }],
      toolCalls: [{ isExecuting: false, isCancelled: true }],
    });
    expect(currentMessage().toolCalls?.[0].result).toBeUndefined();
    expect(useChatStore.getState()).toMatchObject({ isStreaming: false, activeRunSessionId: null, abortController: null });
    expect(stopChatRuntime()).toBe(false);
  });

  it("ignores old callbacks after a stopped conversation restarts", () => {
    const old = callbacks;
    stopChatRuntime();
    const stopped = currentMessage();
    expect(startChatRuntime({ input: "重新分析", history: [] })).toBe(true);
    old.onDelta({ type: "round_completed", research_round: { ...round, status: "completed" } });
    old.onDelta({ type: "tool_call", tool_call: { id: "late", type: "function", function: { name: "web_fetch", arguments: "{}" } } });
    old.onDelta({ type: "text", content: "迟到回答" });
    old.onDelta({ type: "done", status: "completed" });
    old.onDone();
    old.onError(new Error("迟到异常"));
    expect(useChatStore.getState().messages.find((message) => message.id === stopped.id)).toBe(stopped);
    expect(currentMessage()).toMatchObject({ isStreaming: true, content: "", toolCalls: [] });
    callbacks.onDelta({ type: "text", content: "新的答案" });
    callbacks.onDelta({ type: "done", status: "completed" });
    expect(currentMessage()).toMatchObject({ isStreaming: false, content: "新的答案", processOutcome: "completed" });
  });

  it.each(["event", "connection"])("settles failure immediately on a %s error without waiting for EOF", (source) => {
    if (source === "event") callbacks.onDelta({ type: "error", error: "服务失败" });
    else callbacks.onError(new Error("连接中断"));
    expect(currentMessage()).toMatchObject({
      isStreaming: false, processOutcome: "failed",
      plan: { steps: [{ status: "failed" }] },
      processUpdates: [{ round: { status: "failed" } }],
      toolCalls: [{ isExecuting: false, isError: true, isCancelled: false }],
    });
    callbacks.onDelta({ type: "done", status: "completed" });
    callbacks.onDone();
    expect(currentMessage().processOutcome).toBe("failed");
    expect(useChatStore.getState().isStreaming).toBe(false);
  });

  it("commits a completed event before EOF and cannot then be cancelled or fail", () => {
    callbacks.onDelta({ type: "tool_result", tool_result: { tool_call_id: "tool", name: "web_fetch", content: "公告证据", is_error: false } });
    callbacks.onDelta({ type: "round_completed", research_round: { ...round, status: "completed" } });
    callbacks.onDelta({ type: "plan_step", plan_step: { step_id: "verify", status: "completed", attempt: 1 } });
    callbacks.onDelta({ type: "done", status: "completed" });
    expect(useChatStore.getState().isStreaming).toBe(false);
    expect(stopChatRuntime()).toBe(false);
    callbacks.onError(new Error("结束后断开"));
    callbacks.onDone();
    expect(currentMessage()).toMatchObject({
      isStreaming: false, processOutcome: "completed", content: "已生成内容",
      plan: { steps: [{ status: "completed" }] },
      processUpdates: [{ round: { status: "completed" } }],
      toolCalls: [{ isExecuting: false, result: "公告证据" }],
    });
  });
});
