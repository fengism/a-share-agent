import type { SessionMeta } from "./chatPersistence";
import { normalizePersistedChatState } from "./chatStoreHelpers";
import type { UserChatState } from "./chatStoreHelpers";
import type { ChatState } from "./chatStoreTypes";
import type { ChatStoreGet, ChatStoreSet, PersistChatStore } from "./chatStoreSliceTypes";

type ChatSessionSlice = Pick<
  ChatState,
  | "messages"
  | "history"
  | "agentNames"
  | "skillNames"
  | "sessions"
  | "activeSessionId"
  | "sessionData"
  | "hydrateSessions"
  | "createSession"
  | "setActiveSession"
  | "deleteSession"
  | "renameSession"
  | "setAgentNames"
  | "setSkillNames"
  | "syncSessionTitle"
>;

export function createChatSessionSlice(
  set: ChatStoreSet,
  get: ChatStoreGet,
  persist: PersistChatStore,
  scopedState: UserChatState,
): ChatSessionSlice {
  return {
    messages: scopedState.messages,
    history: scopedState.history,
    agentNames: scopedState.agentNames,
    skillNames: scopedState.skillNames,
    sessions: scopedState.sessions,
    activeSessionId: scopedState.activeSessionId,
    sessionData: scopedState.sessionData,

    hydrateSessions: (snapshot) => {
      if (get().isStreaming) return;
      const hydrated = normalizePersistedChatState(snapshot);
      set({
        messages: hydrated.messages,
        history: hydrated.history,
        agentNames: hydrated.agentNames,
        skillNames: hydrated.skillNames,
        isStreaming: false,
        activeRunSessionId: null,
        activeRunLabel: null,
        syncStatus: "synced",
        abortController: null,
        sessions: hydrated.sessions,
        activeSessionId: hydrated.activeSessionId,
        sessionData: hydrated.sessionData,
      });
      persist();
    },

    createSession: () => {
      const state = get();
      const timestamp = Date.now();
      let sequence = 0;
      let id = `session-${timestamp}`;
      while (state.sessions.some((session) => session.id === id)) {
        sequence += 1;
        id = `session-${timestamp}-${sequence}`;
      }
      const newSession: SessionMeta = {
        id,
        title: "新对话",
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };
      const nextSessionData = { ...state.sessionData };
      if (state.activeSessionId) {
        nextSessionData[state.activeSessionId] = {
          messages: state.messages,
          history: state.history,
          agentNames: state.agentNames,
          skillNames: state.skillNames,
        };
      }
      set({
        sessions: [...state.sessions, newSession],
        activeSessionId: id,
        sessionData: {
          ...nextSessionData,
          [id]: { messages: [], history: [], agentNames: null, skillNames: null },
        },
        messages: [],
        history: [],
        agentNames: null,
        skillNames: null,
      });
      persist();
      return id;
    },

    setActiveSession: (sessionId) => {
      const state = get();
      if (sessionId === state.activeSessionId) return;
      const nextSessionData = { ...state.sessionData };
      if (state.activeSessionId) {
        nextSessionData[state.activeSessionId] = {
          messages: state.messages,
          history: state.history,
          agentNames: state.agentNames,
          skillNames: state.skillNames,
        };
      }
      const newData = nextSessionData[sessionId] || {
        messages: [],
        history: [],
        agentNames: null,
        skillNames: null,
      };
      set({
        activeSessionId: sessionId,
        sessionData: nextSessionData,
        messages: newData.messages,
        history: newData.history,
        agentNames: newData.agentNames ?? null,
        skillNames: newData.skillNames ?? null,
      });
      persist();
    },

    deleteSession: (sessionId) => {
      const state = get();
      if (state.sessions.length <= 1) return;
      const newSessions = state.sessions.filter((session) => session.id !== sessionId);
      const newSessionData = { ...state.sessionData };
      delete newSessionData[sessionId];
      let newActiveId = state.activeSessionId;
      let newMessages = state.messages;
      let newHistory = state.history;
      let newAgentNames = state.agentNames;
      let newSkillNames = state.skillNames;
      if (sessionId === state.activeSessionId) {
        const fallback = newSessions[0];
        newActiveId = fallback.id;
        const fallbackData = newSessionData[fallback.id] || {
          messages: [],
          history: [],
          agentNames: null,
          skillNames: null,
        };
        newMessages = fallbackData.messages;
        newHistory = fallbackData.history;
        newAgentNames = fallbackData.agentNames ?? null;
        newSkillNames = fallbackData.skillNames ?? null;
      }
      set({
        sessions: newSessions,
        sessionData: newSessionData,
        activeSessionId: newActiveId,
        messages: newMessages,
        history: newHistory,
        agentNames: newAgentNames,
        skillNames: newSkillNames,
      });
      persist();
    },

    renameSession: (sessionId, title) => {
      set((state) => ({
        sessions: state.sessions.map((session) => (
          session.id === sessionId ? { ...session, title, updatedAt: Date.now() } : session
        )),
      }));
      persist();
    },

    setAgentNames: (agentNames) => {
      set({ agentNames: agentNames === null ? null : [...agentNames] });
      persist();
    },

    setSkillNames: (skillNames) => {
      set({ skillNames: skillNames === null ? null : [...skillNames] });
      persist();
    },

    syncSessionTitle: () => {
      const state = get();
      if (!state.activeSessionId || state.messages.length === 0) return;
      const firstUserMessage = state.messages.find((message) => message.role === "user");
      if (!firstUserMessage) return;
      const session = state.sessions.find((item) => item.id === state.activeSessionId);
      if (!session || session.title !== "新对话") return;
      const title = firstUserMessage.content.length > 20
        ? `${firstUserMessage.content.slice(0, 20)}…`
        : firstUserMessage.content;
      get().renameSession(state.activeSessionId, title);
    },
  };
}
