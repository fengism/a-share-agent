import { describe, expect, it } from "vitest";
import type { ChatDisplayMessage, ChatMessage } from "../types/chat";
import {
  loadUserChatState,
  prepareLastAssistantRegeneration,
  prepareUserMessageEdit,
  updateMessageById,
  upsertAssistantHistory,
} from "./chatStoreHelpers";

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

describe("chat store helpers", () => {
  it("creates a usable default session for an empty user scope", () => {
    const state = loadUserChatState(createMemoryStorage(), null);

    expect(state.sessions).toHaveLength(1);
    expect(state.activeSessionId).toBe(state.sessions[0].id);
    expect(state.sessionData[state.sessions[0].id]).toEqual({
      messages: [],
      history: [],
      agentNames: null,
      skillNames: null,
    });
    expect(state.messages).toEqual([]);
    expect(state.history).toEqual([]);
  });

  it("falls back to the first persisted session when the active id is invalid", () => {
    const storage = createMemoryStorage();
    const message: ChatDisplayMessage = { id: "message-1", role: "user", content: "问题" };
    storage.setItem("chat-sessions:user:7", JSON.stringify({
      sessions: [{ id: "first", title: "会话", createdAt: 1, updatedAt: 1 }],
      activeSessionId: "missing",
    }));
    storage.setItem("chat-sessions:user:7-data", JSON.stringify({
      first: { messages: [message], history: [{ role: "user", content: "问题" }] },
    }));

    const state = loadUserChatState(storage, 7);

    expect(state.activeSessionId).toBe("first");
    expect(state.messages).toEqual([message]);
  });

  it("updates only the targeted display message", () => {
    const messages: ChatDisplayMessage[] = [
      { id: "first", role: "user", content: "问题" },
      { id: "second", role: "assistant", content: "旧答案" },
    ];

    const updated = updateMessageById(messages, "second", (message) => ({
      ...message,
      content: "新答案",
    }));

    expect(updated[0]).toBe(messages[0]);
    expect(updated[1].content).toBe("新答案");
  });

  it("prepares the last completed turn for regeneration", () => {
    const messages: ChatDisplayMessage[] = [
      { id: "user-1", role: "user", content: "第一个问题" },
      { id: "assistant-1", role: "assistant", content: "第一个回答", isStreaming: false },
      { id: "user-2", role: "user", content: "第二个问题" },
      { id: "assistant-2", role: "assistant", content: "第二个回答", isStreaming: false },
    ];
    const history: ChatMessage[] = [
      { role: "user", content: "第一个问题" },
      { role: "assistant", content: "第一个回答" },
      { role: "user", content: "第二个问题" },
      { role: "assistant", content: "第二个回答" },
    ];

    const prepared = prepareLastAssistantRegeneration(messages, history);

    expect(prepared).toEqual({
      message: "第二个问题",
      history: history.slice(0, 2),
      nextMessages: messages.slice(0, 3),
      nextHistory: history.slice(0, 3),
    });
  });

  it("does not regenerate an unfinished or unanswered turn", () => {
    const history: ChatMessage[] = [{ role: "user", content: "问题" }];

    expect(prepareLastAssistantRegeneration(
      [{ id: "user", role: "user", content: "问题" }],
      history,
    )).toBeNull();
    expect(prepareLastAssistantRegeneration(
      [
        { id: "user", role: "user", content: "问题" },
        { id: "assistant", role: "assistant", content: "回答", isStreaming: true },
      ],
      history,
    )).toBeNull();
  });

  it("finalizes assistant history without transient tool messages", () => {
    const history: ChatMessage[] = [
      { role: "user", content: "问题" },
      {
        role: "assistant",
        content: null,
        reasoning_content: "推理",
        tool_calls: [{
          id: "tool-1",
          type: "function",
          function: { name: "web_search", arguments: "{}" },
        }],
      },
      { role: "tool", content: "结果", tool_call_id: "tool-1" },
    ];

    expect(upsertAssistantHistory(history, "最终答案")).toEqual([
      { role: "user", content: "问题" },
      {
        role: "assistant",
        content: "最终答案",
        reasoning_content: undefined,
        tool_calls: undefined,
      },
    ]);
  });
});

function editUserMessage(id: string, content: string): ChatDisplayMessage {
  return { id, role: "user", content };
}

function editAssistantMessage(id: string, content: string): ChatDisplayMessage {
  return { id, role: "assistant", content };
}

describe("prepareUserMessageEdit", () => {
  it("rewrites the target entry and truncates later conversation", () => {
    const messages = [
      editUserMessage("m1", "第一条"),
      editAssistantMessage("m2", "第一个回答"),
      editUserMessage("m3", "第二条"),
      editAssistantMessage("m4", "第二个回答"),
    ];
    const history: ChatMessage[] = [
      { role: "user", content: "第一条" },
      { role: "assistant", content: "第一个回答" },
      { role: "user", content: "第二条" },
      { role: "assistant", content: "第二个回答" },
    ];

    const prepared = prepareUserMessageEdit(messages, history, "m3", "  改后的第二条  ");

    expect(prepared).not.toBeNull();
    expect(prepared!.message).toBe("改后的第二条");
    expect(prepared!.history).toEqual([
      { role: "user", content: "第一条" },
      { role: "assistant", content: "第一个回答" },
    ]);
    expect(prepared!.nextMessages).toEqual([
      expect.objectContaining({ id: "m1", content: "第一条" }),
      expect.objectContaining({ id: "m2" }),
      expect.objectContaining({ id: "m3", content: "改后的第二条" }),
    ]);
    expect(prepared!.nextHistory).toEqual([
      { role: "user", content: "第一条" },
      { role: "assistant", content: "第一个回答" },
      { role: "user", content: "改后的第二条" },
    ]);
  });

  it("locates entries by ordinal so duplicate contents stay independent", () => {
    const messages = [
      editUserMessage("m1", "重复"),
      editAssistantMessage("m2", "答1"),
      editUserMessage("m3", "重复"),
      editAssistantMessage("m4", "答2"),
    ];
    const history: ChatMessage[] = [
      { role: "user", content: "重复" },
      { role: "assistant", content: "答1" },
      { role: "user", content: "重复" },
      { role: "assistant", content: "答2" },
    ];

    const prepared = prepareUserMessageEdit(messages, history, "m1", "改第一条");

    expect(prepared!.nextMessages).toEqual([expect.objectContaining({ id: "m1", content: "改第一条" })]);
    expect(prepared!.nextHistory).toEqual([{ role: "user", content: "改第一条" }]);
    expect(prepared!.history).toEqual([]);
  });

  it("rejects blank content, unknown or non-user ids, and orphaned history", () => {
    const messages = [editUserMessage("m1", "第一条"), editAssistantMessage("m2", "回答")];
    const history: ChatMessage[] = [{ role: "assistant", content: "孤立回答" }];

    expect(prepareUserMessageEdit(messages, history, "m1", "   ")).toBeNull();
    expect(prepareUserMessageEdit(messages, history, "missing", "新内容")).toBeNull();
    expect(prepareUserMessageEdit(messages, history, "m2", "新内容")).toBeNull();
    expect(prepareUserMessageEdit(messages, history, "m1", "新内容")).toBeNull();
  });
});
