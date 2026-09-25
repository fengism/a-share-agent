import type { ChatStateContent, ChatStateSnapshot } from "../api/chatSessions";
import { compactChatSessionData, type PersistedChatState, type SessionData } from "./chatPersistence";
import { sanitizeDisplayMessages, sanitizeHistoryMessages } from "./chatMessageGuards";
import type { ChatState } from "./chatStoreTypes";
import type { ChatMessage } from "../types/chat";

// Below the backend's 1M code-point limit, leaving room for metadata and revision.
// Include history defaults BEFORE measuring: 3,000 messages can add >100K chars.
export const CHAT_REMOTE_DATA_LIMIT = 900_000;

function boundedHistory(message: ChatMessage): ChatMessage {
  return {
    role: message.role,
    content: message.content?.slice(0, 100_000) ?? null,
    reasoning_content: message.reasoning_content?.slice(0, 100_000) ?? null,
    tool_call_id: message.tool_call_id ?? null,
    name: message.name ?? null,
    tool_calls: message.tool_calls?.slice(0, 32).map((call) => ({
      ...call,
      type: "function",
      function: { ...call.function, arguments: call.function.arguments.slice(0, 100_000) },
    })) ?? null,
  };
}

export function toServerChatState(state: ChatState): ChatStateContent {
  const sessionData = { ...state.sessionData };
  if (state.activeSessionId) {
    sessionData[state.activeSessionId] = {
      messages: state.messages,
      history: state.history,
      agentNames: state.agentNames,
      skillNames: state.skillNames,
    };
  }
  const sessions = [...state.sessions]
    .sort((a, b) => Number(b.id === state.activeSessionId) - Number(a.id === state.activeSessionId) || b.updatedAt - a.updatedAt)
    .slice(0, 30);
  const boundedData = Object.fromEntries(sessions.flatMap(({ id }) => {
    const data = sessionData[id];
    return data ? [[id, {
      ...data, messages: data.messages.slice(-200), history: data.history.slice(-100).map(boundedHistory),
      agentNames: data.agentNames?.slice(0, 16), skillNames: data.skillNames?.slice(0, 32),
    }]] : [];
  }));
  const compacted = compactChatSessionData(sessions, boundedData, state.activeSessionId, CHAT_REMOTE_DATA_LIMIT);
  if (!compacted.fits) throw new Error("会话过大，无法安全同步；本地内容已保留");
  return {
    sessions: sessions.map((session) => ({
      id: session.id,
      title: session.title,
      created_at: session.createdAt,
      updated_at: session.updatedAt,
    })),
    session_data: Object.fromEntries(Object.entries(compacted.sessionData).map(([sessionId, data]) => [
      sessionId,
      {
        messages: data.messages as unknown as Array<Record<string, unknown>>,
        history: data.history,
        agent_names: data.agentNames,
        skill_names: data.skillNames,
      },
    ])),
    active_session_id: state.activeSessionId,
  };
}

export function fromServerChatState(state: ChatStateSnapshot): PersistedChatState {
  const sessionData: Record<string, SessionData> = {};
  for (const [sessionId, data] of Object.entries(state.session_data)) {
    sessionData[sessionId] = {
      messages: sanitizeDisplayMessages(data.messages),
      history: sanitizeHistoryMessages(data.history),
      agentNames: data.agent_names ?? null,
      skillNames: data.skill_names ?? null,
    };
  }
  return {
    sessions: state.sessions.map((session) => ({
      id: session.id,
      title: session.title,
      createdAt: session.created_at,
      updatedAt: session.updated_at,
    })),
    sessionData,
    activeSessionId: state.active_session_id ?? null,
  };
}
