import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setActiveUserScope } from "./userScope";
import { useChatStore } from "./chatStore";

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
});
