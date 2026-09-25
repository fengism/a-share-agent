import { describe, expect, it } from "vitest";
import { fromServerChatState, toServerChatState } from "./chatServerSync";
import type { ChatState } from "./chatStoreTypes";

describe("chat server sync conversion", () => {
  it("uses live active-session messages instead of stale cached data", () => {
    const state = {
      sessions: [{ id: "session-1", title: "茅台", createdAt: 1, updatedAt: 2 }],
      activeSessionId: "session-1",
      sessionData: {
        "session-1": { messages: [], history: [], agentNames: null, skillNames: null },
      },
      messages: [{ id: "message-1", role: "user", content: "分析茅台" }],
      history: [{ role: "user", content: "分析茅台" }],
      agentNames: ["fundamental"],
      skillNames: ["stock_analysis"],
    } as unknown as ChatState;

    const remote = toServerChatState(state);
    expect(remote.session_data["session-1"].messages).toEqual(state.messages);
    expect(fromServerChatState({ ...remote, revision: 1 })).toMatchObject({
      activeSessionId: "session-1",
      sessions: [{ id: "session-1", createdAt: 1, updatedAt: 2 }],
      sessionData: {
        "session-1": { agentNames: ["fundamental"], skillNames: ["stock_analysis"] },
      },
    });
  });
});

it("fits the server budget by discarding reasoning before answers without mutating live state", () => {
  const messages = Array.from({ length: 12 }, (_, index) => ({
    id: `m-${index}`, role: "assistant", content: `answer ${index}`,
    reasoningContent: "推".repeat(90_000),
  }));
  const state = {
    sessions: [{ id: "s", title: "会话", createdAt: 1, updatedAt: 1 }],
    sessionData: {}, activeSessionId: "s", messages, history: [], agentNames: null, skillNames: null,
  } as unknown as ChatState;
  const snapshot = toServerChatState(state);
  expect(JSON.stringify({ ...snapshot, revision: 100 }).length).toBeLessThan(1_000_000);
  expect(snapshot.session_data.s.messages!.map((m) => m.content)).toEqual(messages.map((m) => m.content));
  expect(messages[0].reasoningContent).toHaveLength(90_000);
});

it("budgets server history defaults across the maximum session count", () => {
  const sessions = Array.from({ length: 30 }, (_, i) => ({ id: `s${i}`, title: "session", createdAt: i, updatedAt: i }));
  const data = () => ({ messages: [], history: Array.from({ length: 100 }, () => ({ role: "user", content: "x".repeat(255) })) });
  const state = { sessions, sessionData: Object.fromEntries(sessions.map((s) => [s.id, data()])),
    activeSessionId: "s29", ...data(), agentNames: null, skillNames: null,
  } as unknown as ChatState;
  const snapshot = toServerChatState(state);
  // Emulate defaults filled by ChatSessionData/AgentMessage validation on the server.
  const normalized = { ...snapshot, revision: 100, session_data: Object.fromEntries(Object.entries(snapshot.session_data).map(([id, entry]) => [id, {
    agent_names: null, skill_names: null, ...entry,
    history: entry.history?.map((m) => ({ content: null, tool_calls: null, tool_call_id: null, name: null, reasoning_content: null, ...m })),
  }])) };
  expect(JSON.stringify(normalized).length).toBeLessThan(1_000_000);
  expect(state.sessionData.s0.history).toHaveLength(100);
});

it("bounds individual model-history fields without altering display answers or local history", () => {
  const content = "x".repeat(120_000);
  const tool_calls = Array.from({ length: 33 }, (_, i) => ({ id: `t${i}`, type: "function", function: { name: "quote", arguments: "{}" } }));
  const state = { sessions: [{ id: "s", title: "session", createdAt: 1, updatedAt: 1 }], sessionData: {}, activeSessionId: "s",
    messages: [{ id: "m", role: "assistant", content }],
    history: [{ role: "assistant", content, reasoning_content: content, tool_calls }], agentNames: null, skillNames: null,
  } as unknown as ChatState;
  const snapshot = toServerChatState(state);
  expect(snapshot.session_data.s.messages![0].content).toHaveLength(120_000);
  expect(snapshot.session_data.s.history![0].content).toHaveLength(100_000);
  expect(snapshot.session_data.s.history![0].reasoning_content).toHaveLength(100_000);
  expect(snapshot.session_data.s.history![0].tool_calls).toHaveLength(32);
  expect(state.history[0].content).toHaveLength(120_000);
  expect(state.history[0].tool_calls).toHaveLength(33);
});
