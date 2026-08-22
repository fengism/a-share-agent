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
