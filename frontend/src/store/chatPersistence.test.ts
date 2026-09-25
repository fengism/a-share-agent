import { describe, expect, it, vi } from "vitest";
import {
  chatStorageKey,
  compactChatSessionData,
  loadPersistedChat,
  persistChatSnapshot,
  type PersistedChatState,
  type SessionData,
  type SessionMeta,
} from "./chatPersistence";

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

function session(id: string, updatedAt: number): SessionMeta {
  return { id, title: id, createdAt: updatedAt, updatedAt };
}

function data(content: string): SessionData {
  return {
    messages: [{ id: "message", role: "assistant", content }],
    history: [{ role: "assistant", content }],
  };
}

describe("chat persistence", () => {
  it("keeps valid metadata when session data JSON is damaged", () => {
    const storage = createMemoryStorage();
    const key = chatStorageKey(7);
    storage.setItem(key, JSON.stringify({ sessions: [session("active", 1)], activeSessionId: "active" }));
    storage.setItem(`${key}-data`, "{");
    const warn = vi.fn();

    const loaded = loadPersistedChat(storage, 7, warn);

    expect(loaded.sessions).toEqual([session("active", 1)]);
    expect(loaded.activeSessionId).toBe("active");
    expect(loaded.sessionData).toEqual({});
    expect(warn).toHaveBeenCalledOnce();
  });

  it("drops old session bodies before compacting the active session", () => {
    const sessions = [session("old", 1), session("active", 2)];
    const sessionData = {
      old: data("o".repeat(800)),
      active: data("a".repeat(400)),
    };

    const compacted = compactChatSessionData(sessions, sessionData, "active", 700);

    expect(compacted.fits).toBe(true);
    expect(compacted.compacted).toBe(true);
    expect(compacted.serialized.length).toBeLessThanOrEqual(700);
    expect(compacted.sessionData.old).toBeUndefined();
    expect(sessionData.old.messages[0].content).toHaveLength(800);
  });

  it("bounds oversized active message and model history", () => {
    const sessions = [session("active", 1)];
    const sessionData = { active: data("x".repeat(5000)) };

    const compacted = compactChatSessionData(sessions, sessionData, "active", 600);

    expect(compacted.fits).toBe(true);
    expect(compacted.serialized.length).toBeLessThanOrEqual(600);
    expect(compacted.sessionData.active.messages[0].content.length).toBeLessThan(5000);
  });

  it("compacts plan summaries and step details with the active message", () => {
    const sessions = [session("active", 1)];
    const sessionData = {
      active: {
        messages: [{
          id: "message",
          role: "assistant" as const,
          content: "回答",
          plan: {
            summary: "规划".repeat(1000),
            steps: [{
              id: "technical",
              title: "技术分析",
              description: "目标".repeat(1000),
              dependencies: [],
              status: "completed" as const,
              detail: "结果".repeat(1000),
              attempt: 1,
            }],
          },
        }],
        history: [{ role: "assistant" as const, content: "回答" }],
      },
    };

    const compacted = compactChatSessionData(sessions, sessionData, "active", 900);

    expect(compacted.fits).toBe(true);
    expect(compacted.sessionData.active.messages[0].plan?.summary?.length).toBeLessThan(2000);
    expect(compacted.sessionData.active.messages[0].plan?.steps[0].detail?.length).toBeLessThan(2000);
  });

  it("writes metadata and data only to the scoped user keys", () => {
    const storage = createMemoryStorage();
    const snapshot: PersistedChatState = {
      sessions: [session("active", 1)],
      sessionData: { active: data("hello") },
      activeSessionId: "active",
    };

    expect(persistChatSnapshot(storage, 9, snapshot)).toBe(true);
    expect(storage.getItem("chat-sessions:user:9")).toContain("active");
    expect(storage.getItem("chat-sessions:user:9-data")).toContain("hello");
    expect(storage.getItem("chat-sessions:user:8")).toBeNull();
  });
  it("drops bulky process records before losing the final answer under storage pressure", () => {
    const sessionData = { active: data("最终结论") };
    sessionData.active.messages[0].processUpdates = Array.from({ length: 60 }, (_, i) => ({ type: "status", content: `${i}: ${"过程".repeat(900)}` }));
    const compacted = compactChatSessionData([session("active", 1)], sessionData, "active", 600);
    expect(compacted.fits).toBe(true);
    expect(compacted.sessionData.active.messages[0].content).toBe("最终结论");
    expect(compacted.sessionData.active.messages[0].processUpdates).toBeUndefined();
    expect(sessionData.active.messages[0].processUpdates).toHaveLength(60);
  });

  it("restores provider reasoning for display without adding it to model history", () => {
    const storage = createMemoryStorage();
    const sessionData = { active: data("最终答案") };
    sessionData.active.messages[0].reasoningContent = "先核验公告，再比较财务指标";
    const snapshot = { sessions: [session("active", 1)], sessionData, activeSessionId: "active" };
    expect(persistChatSnapshot(storage, 9, snapshot)).toBe(true);
    const restored = loadPersistedChat(storage, 9);
    expect(restored.sessionData.active.messages[0].reasoningContent).toBe("先核验公告，再比较财务指标");
    expect(restored.sessionData.active.history).toEqual([{ role: "assistant", content: "最终答案" }]);
  });

});

it("round-trips reasoning boundaries, filters corrupt offsets and drops metadata when compacting", () => {
  const storage = createMemoryStorage();
  const sessionData = { active: data("答案") };
  sessionData.active.messages[0].reasoningContent = "推理".repeat(1000);
  const block = { block_id: "a", source: "分析", stage: "agent" as const, turn: 1, attempt: 2, start: 0, end: 2000 };
  sessionData.active.messages[0].reasoningBlocks = [block, { ...block, end: 9999 }];
  expect(persistChatSnapshot(storage, 1, { sessions: [session("active", 1)], sessionData, activeSessionId: "active" })).toBe(true);
  expect(loadPersistedChat(storage, 1).sessionData.active.messages[0].reasoningBlocks).toEqual([block]);
  const compacted = compactChatSessionData([session("active", 1)], sessionData, "active", 600);
  expect(compacted.sessionData.active.messages[0].reasoningContent).toBeUndefined();
  expect(compacted.sessionData.active.messages[0].reasoningBlocks).toBeUndefined();
  expect(compacted.sessionData.active.messages[0].content).toBe("答案");
});
