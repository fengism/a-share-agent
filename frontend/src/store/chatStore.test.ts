import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setActiveUserScope } from "./userScope";
import { useChatStore } from "./chatStore";
import { fromServerChatState, toServerChatState } from "./chatServerSync";

function createMemoryStorage(): Storage {
  const values = new Map<string, string>();
  return {
    get length() {
      return values.size;
    },
    clear: () => values.clear(),
    getItem: (key) => values.get(key) ?? null,
    key: (index) => [...values.keys()][index] ?? null,
    removeItem: (key) => values.delete(key),
    setItem: (key, value) => values.set(key, value),
  };
}

describe("chatStore user scope", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: createMemoryStorage(),
    });
    setActiveUserScope(null);
    window.localStorage.clear();
  });

  afterEach(() => {
    setActiveUserScope(null);
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it("keeps each user's history separate and restores it on return", () => {
    setActiveUserScope(1);
    useChatStore.getState().addUserMessage("用户一的问题");
    useChatStore.getState().syncSessionTitle();
    vi.advanceTimersByTime(300);

    setActiveUserScope(2);
    expect(useChatStore.getState().messages).toEqual([]);
    useChatStore.getState().addUserMessage("用户二的问题");
    useChatStore.getState().syncSessionTitle();
    vi.advanceTimersByTime(300);

    setActiveUserScope(1);
    expect(useChatStore.getState().messages).toEqual([
      expect.objectContaining({ role: "user", content: "用户一的问题" }),
    ]);

    setActiveUserScope(2);
    expect(useChatStore.getState().messages).toEqual([
      expect.objectContaining({ role: "user", content: "用户二的问题" }),
    ]);
  });

  it("flushes a pending write to its original user key", () => {
    setActiveUserScope(1);
    useChatStore.getState().addUserMessage("只属于用户一");
    useChatStore.getState().syncSessionTitle();

    setActiveUserScope(2);
    vi.runOnlyPendingTimers();

    expect(window.localStorage.getItem("chat-sessions:user:1")).not.toBeNull();
    expect(window.localStorage.getItem("chat-sessions:user:2")).toBeNull();
    expect(window.localStorage.getItem("chat-sessions:user:1-data")).toContain("只属于用户一");
  });

  it("ignores legacy unscoped chat history", () => {
    window.localStorage.setItem("chat-sessions", JSON.stringify({
      sessions: [{ id: "legacy", title: "旧对话", createdAt: 1, updatedAt: 1 }],
      activeSessionId: "legacy",
    }));
    window.localStorage.setItem("chat-sessions-data", JSON.stringify({
      legacy: { messages: [{ id: "old", role: "user", content: "旧账号内容" }], history: [] },
    }));

    setActiveUserScope(3);

    expect(useChatStore.getState().messages).toEqual([]);
    expect(useChatStore.getState().sessions).toHaveLength(1);
    expect(useChatStore.getState().sessions[0].id).not.toBe("legacy");
  });

  it("aborts an active stream when the user changes", () => {
    setActiveUserScope(1);
    const controller = new AbortController();
    const abortSpy = vi.spyOn(controller, "abort");
    useChatStore.getState().setAbortController(controller);
    useChatStore.getState().setStreaming(true);

    setActiveUserScope(2);

    expect(abortSpy).toHaveBeenCalledOnce();
    expect(useChatStore.getState().abortController).toBeNull();
    expect(useChatStore.getState().isStreaming).toBe(false);
  });

  it("truncates later conversation when a user message is edited", () => {
    setActiveUserScope(1);
    useChatStore.getState().addUserMessage("第一条");
    useChatStore.getState().addAssistantMessage("assistant-edit-1");
    useChatStore.getState().appendToAssistant("assistant-edit-1", "答1");
    useChatStore.getState().finalizeMessage("assistant-edit-1");
    useChatStore.getState().addUserMessage("第二条");

    const firstId = useChatStore.getState().messages[0].id;
    const request = useChatStore.getState().editUserMessage(firstId, "第一条（改）");

    expect(request).toEqual({ message: "第一条（改）", history: [] });
    expect(useChatStore.getState().messages).toEqual([
      expect.objectContaining({ role: "user", content: "第一条（改）" }),
    ]);
    expect(useChatStore.getState().history).toEqual([
      { role: "user", content: "第一条（改）" },
    ]);
  });

  it("rejects user message edits while streaming", () => {
    setActiveUserScope(1);
    useChatStore.getState().addUserMessage("第一条");
    useChatStore.getState().setStreaming(true);

    const firstId = useChatStore.getState().messages[0].id;
    expect(useChatStore.getState().editUserMessage(firstId, "改")).toBeNull();
    expect(useChatStore.getState().messages[0].content).toBe("第一条");

    useChatStore.getState().setStreaming(false);
    expect(useChatStore.getState().editUserMessage(firstId, "改")).not.toBeNull();
  });

  it("removes the previous assistant response before regeneration", () => {
    setActiveUserScope(1);
    useChatStore.getState().addUserMessage("分析贵州茅台");
    useChatStore.getState().addAssistantMessage("assistant-1");
    useChatStore.getState().appendToAssistant("assistant-1", "旧回答");
    useChatStore.getState().finalizeMessage("assistant-1");

    const request = useChatStore.getState().regenerateLastAssistant();

    expect(request).toEqual({ message: "分析贵州茅台", history: [] });
    expect(useChatStore.getState().messages).toEqual([
      expect.objectContaining({ role: "user", content: "分析贵州茅台" }),
    ]);
    expect(useChatStore.getState().history).toEqual([
      { role: "user", content: "分析贵州茅台" },
    ]);
  });

  it("tracks plan progress and cancels unfinished steps when stopped", () => {
    setActiveUserScope(1);
    useChatStore.getState().addAssistantMessage("assistant-plan");
    useChatStore.getState().setAssistantPlan("assistant-plan", {
      summary: "分两步分析",
      steps: [
        {
          id: "technical",
          title: "技术分析",
          dependencies: [],
          status: "pending",
          attempt: 0,
        },
        {
          id: "risk",
          title: "风险分析",
          dependencies: ["technical"],
          status: "pending",
          attempt: 0,
        },
      ],
    });
    useChatStore.getState().updateAssistantPlanStep("assistant-plan", {
      step_id: "technical",
      status: "completed",
      detail: "分析完成",
      attempt: 1,
    });

    useChatStore.getState().finalizeMessage("assistant-plan");

    const plan = useChatStore.getState().messages[0].plan;
    expect(plan?.steps[0]).toEqual(expect.objectContaining({
      status: "completed",
      attempt: 1,
    }));
    expect(plan?.steps[1]).toEqual(expect.objectContaining({
      status: "cancelled",
      detail: "执行已停止",
    }));
  });

  it("keeps capability overrides isolated per chat session", () => {
    setActiveUserScope(1);
    const firstSessionId = useChatStore.getState().activeSessionId;
    useChatStore.getState().setAgentNames(["risk"]);
    useChatStore.getState().setSkillNames(["market_data"]);

    const secondSessionId = useChatStore.getState().createSession();
    expect(useChatStore.getState().agentNames).toBeNull();
    expect(useChatStore.getState().skillNames).toBeNull();

    useChatStore.getState().setAgentNames([]);
    useChatStore.getState().setSkillNames([]);
    useChatStore.getState().setActiveSession(firstSessionId!);
    expect(useChatStore.getState().agentNames).toEqual(["risk"]);
    expect(useChatStore.getState().skillNames).toEqual(["market_data"]);

    useChatStore.getState().setActiveSession(secondSessionId);
    expect(useChatStore.getState().agentNames).toEqual([]);
    expect(useChatStore.getState().skillNames).toEqual([]);
  });
  it("persists public process records and terminal status independently of answer history", () => {
    setActiveUserScope(1);
    const store = useChatStore.getState();
    store.addAssistantMessage("process-history");
    store.setAssistantStatus("process-history", "核对一手资料");
    store.appendToAssistant("process-history", "最终结论");
    store.finalizeMessage("process-history", "partial");
    setActiveUserScope(2);
    setActiveUserScope(1);
    expect(useChatStore.getState().messages[useChatStore.getState().messages.length - 1]).toMatchObject({
      content: "最终结论", processOutcome: "partial", isStreaming: false,
      processUpdates: [{ type: "status", content: "核对一手资料" }],
    });
    expect(useChatStore.getState().history[useChatStore.getState().history.length - 1]).not.toHaveProperty("processUpdates");
  });

  it.each(["local", "server"])("settles interrupted %s snapshots for active and inactive sessions", (source) => {
    setActiveUserScope(1);
    const store = useChatStore.getState();
    const firstSession = store.activeSessionId!;
    store.addAssistantMessage("unfinished");
    store.addToolCall("unfinished", { id: "tool", type: "function", function: { name: "web_fetch", arguments: "{}" } });
    store.addAssistantProcessUpdate("unfinished", { type: "round", round: {
      round_index: 1, round_total: 1, status: "running", objective: "核验", evidence_gaps: [], tool_names: [],
      tool_selection_reason: "", evidence_added: ["已有证据"], judgment_basis: [], conclusion: "", next_step: "",
    } });
    // Simulate a snapshot made before the old browser process was interrupted.
    const secondSession = store.createSession();
    store.addAssistantMessage("another-unfinished");
    store.appendToAssistant("another-unfinished", "未完成的回答");
    store.renameSession(secondSession, "保存中的对话");
    if (source === "local") {
      setActiveUserScope(2);
      setActiveUserScope(1);
    } else {
      const snapshot = toServerChatState(useChatStore.getState());
      store.hydrateSessions(fromServerChatState({ ...snapshot, revision: 1 }));
    }
    expect(useChatStore.getState().activeSessionId).toBe(secondSession);
    expect(useChatStore.getState()).toMatchObject({ isStreaming: false, activeRunSessionId: null, abortController: null });
    expect(useChatStore.getState().messages[0]).toMatchObject({ content: "未完成的回答", isStreaming: false, processOutcome: "cancelled" });
    store.setActiveSession(firstSession);
    expect(useChatStore.getState().messages[0]).toMatchObject({
      isStreaming: false, processOutcome: "cancelled",
      toolCalls: [{ isExecuting: false, isCancelled: true }],
      processUpdates: [{ round: { status: "cancelled", evidence_added: ["已有证据"] } }],
    });
  });

  it("persists cancelled round/tool states and cannot finalize the same message as completed later", () => {
    setActiveUserScope(1);
    const store = useChatStore.getState();
    store.addAssistantMessage("cancelled");
    store.addToolCall("cancelled", { id: "tool", type: "function", function: { name: "web_fetch", arguments: "{}" } });
    store.addAssistantProcessUpdate("cancelled", { type: "round", round: {
      round_index: 1, round_total: 1, status: "running", objective: "核验", evidence_gaps: [], tool_names: [],
      tool_selection_reason: "", evidence_added: ["已有证据"], judgment_basis: [], conclusion: "", next_step: "",
    } });
    store.finalizeMessage("cancelled", "cancelled");
    const settled = useChatStore.getState().messages[0];
    store.finalizeMessage("cancelled", "completed");
    expect(useChatStore.getState().messages[0]).toBe(settled);
    const serverSnapshot = toServerChatState(useChatStore.getState());
    setActiveUserScope(2);
    setActiveUserScope(1);
    expect(useChatStore.getState().messages[0]).toEqual(settled);
    store.hydrateSessions(fromServerChatState({ ...serverSnapshot, revision: 1 }));
    expect(useChatStore.getState().messages[0]).toEqual(settled);
  });

});
