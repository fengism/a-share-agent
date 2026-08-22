import type { ChatStateContent, ChatStateSnapshot } from "../api/chatSessions";
import type { ChatDisplayMessage, ChatMessage } from "../types/chat";
import type { PersistedChatState, SessionData } from "./chatPersistence";
import type { ChatState } from "./chatStoreTypes";

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
  return {
    sessions: state.sessions.map((session) => ({
      id: session.id,
      title: session.title,
      created_at: session.createdAt,
      updated_at: session.updatedAt,
    })),
    session_data: Object.fromEntries(Object.entries(sessionData).map(([sessionId, data]) => [
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
      messages: (data.messages ?? []) as unknown as ChatDisplayMessage[],
      history: (data.history ?? []) as ChatMessage[],
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
