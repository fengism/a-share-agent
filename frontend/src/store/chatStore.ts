import { create } from "zustand";
import type {
  ChatDisplayMessage,
  ChatMessage,
  ToolCallDisplay,
  ToolCallInfo,
} from "../types/chat";

// ── 会话管理 ──

export interface SessionMeta {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
}

interface SessionData {
  messages: ChatDisplayMessage[];
  history: ChatMessage[];
}

const STORAGE_KEY = "chat-sessions";

function loadPersisted(): { sessions: SessionMeta[]; sessionData: Record<string, SessionData>; activeSessionId: string | null } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const meta = raw ? JSON.parse(raw) : {};
    const rawData = localStorage.getItem(STORAGE_KEY + "-data");
    const sessionData = rawData ? JSON.parse(rawData) : {};
    return {
      sessions: meta.sessions ?? [],
      sessionData: sessionData ?? {},
      activeSessionId: meta.activeSessionId ?? null,
    };
  } catch { /* ignore */ }
  return { sessions: [], sessionData: {}, activeSessionId: null };
}

function persist(
  sessions: SessionMeta[],
  sessionData: Record<string, SessionData>,
  activeSessionId: string | null,
) {
  try {
    // Only persist session metadata + activeId, not full message data
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ sessions, activeSessionId }));
    // Messages data goes to a separate key to avoid loading too much
    localStorage.setItem(STORAGE_KEY + "-data", JSON.stringify(sessionData));
  } catch {
    // localStorage might be full - silently fail
  }
}

// Interactive ChatState
interface ChatState {
  // Active session
  messages: ChatDisplayMessage[];
  history: ChatMessage[];
  isStreaming: boolean;
  abortController: AbortController | null;

  // Session management
  sessions: SessionMeta[];
  activeSessionId: string | null;
  sessionData: Record<string, SessionData>;

  // Session methods
  createSession: () => string;
  setActiveSession: (sessionId: string) => void;
  deleteSession: (sessionId: string) => void;
  renameSession: (sessionId: string, title: string) => void;
  syncSessionTitle: () => void;

  // Message methods (operate on active session)
  addUserMessage: (content: string) => void;
  addAssistantMessage: (id: string) => void;
  appendToAssistant: (id: string, text: string) => void;
  addToolCall: (messageId: string, tc: ToolCallInfo) => void;
  updateToolResult: (
    messageId: string,
    toolCallId: string,
    result: string,
    isError: boolean,
  ) => void;
  setReasoningContent: (messageId: string, reasoningContent: string) => void;
  appendToReasoning: (messageId: string, text: string) => void;
  setStreaming: (streaming: boolean) => void;
  setAbortController: (controller: AbortController | null) => void;
  clearChat: () => void;
  finalizeMessage: (messageId: string) => void;
}

let _msgCounter = 0;
function nextId() {
  return `msg-${++_msgCounter}`;
}

function updateMessageById(
  messages: ChatDisplayMessage[],
  id: string,
  updater: (message: ChatDisplayMessage) => ChatDisplayMessage,
) {
  return messages.map((message) =>
    message.id === id ? updater(message) : message,
  );
}

function findLastAssistantIndex(history: ChatMessage[]) {
  for (let i = history.length - 1; i >= 0; i--) {
    if (history[i].role === "assistant") {
      return i;
    }
  }
  return -1;
}

function upsertAssistantHistory(
  history: ChatMessage[],
  content: string,
  reasoningContent?: string,
) {
  const nextHistory = [...history];
  const assistantIdx = findLastAssistantIndex(nextHistory);

  if (assistantIdx >= 0) {
    nextHistory[assistantIdx] = {
      ...nextHistory[assistantIdx],
      content,
      reasoning_content: reasoningContent,
    };
  } else {
    nextHistory.push({
      role: "assistant",
      content,
      reasoning_content: reasoningContent,
    });
  }

  return nextHistory;
}

export const useChatStore = create<ChatState>((set, get) => {
  // Restore persisted sessions
  const persisted = loadPersisted();
  const sessions = persisted.sessions;
  const sessionData = persisted.sessionData;
  let activeSessionId = persisted.activeSessionId;

  // Ensure at least one session
  if (sessions.length === 0) {
    const id = `session-${Date.now()}`;
    sessions.push({ id, title: "新对话", createdAt: Date.now(), updatedAt: Date.now() });
    sessionData[id] = { messages: [], history: [] };
    activeSessionId = id;
  }

  const activeData = activeSessionId ? sessionData[activeSessionId] : undefined;

  return {
    // Active session
    messages: activeData?.messages ?? [],
    history: activeData?.history ?? [],
    isStreaming: false,
    abortController: null,

    // Session management
    sessions,
    activeSessionId,
    sessionData,

    createSession: () => {
      const state = get();
      const id = `session-${Date.now()}`;
      const newSession: SessionMeta = {
        id, title: "新对话", createdAt: Date.now(), updatedAt: Date.now(),
      };

      // Save the current session's data
      if (state.activeSessionId) {
        state.sessionData[state.activeSessionId] = {
          messages: state.messages,
          history: state.history,
        };
      }

      set({
        sessions: [...state.sessions, newSession],
        activeSessionId: id,
        sessionData: { ...state.sessionData, [id]: { messages: [], history: [] } },
        messages: [],
        history: [],
      });

      persist(
        get().sessions,
        get().sessionData,
        get().activeSessionId,
      );

      return id;
    },

    setActiveSession: (sessionId) => {
      const state = get();
      if (sessionId === state.activeSessionId) return;

      // Save current session data
      if (state.activeSessionId) {
        state.sessionData[state.activeSessionId] = {
          messages: state.messages,
          history: state.history,
        };
      }

      // Load new session data
      const newData = state.sessionData[sessionId] || { messages: [], history: [] };

      set({
        activeSessionId: sessionId,
        sessionData: { ...state.sessionData },
        messages: newData.messages,
        history: newData.history,
      });

      persist(
        get().sessions,
        get().sessionData,
        get().activeSessionId,
      );
    },

    deleteSession: (sessionId) => {
      const state = get();
      if (state.sessions.length <= 1) return; // Keep at least one session

      const newSessions = state.sessions.filter((s) => s.id !== sessionId);
      const newSessionData = { ...state.sessionData };
      delete newSessionData[sessionId];

      let newActiveId = state.activeSessionId;
      let newMessages = state.messages;
      let newHistory = state.history;

      if (sessionId === state.activeSessionId) {
        // Switch to another session
        const fallback = newSessions[0];
        newActiveId = fallback.id;
        const fallbackData = newSessionData[fallback.id] || { messages: [], history: [] };
        newMessages = fallbackData.messages;
        newHistory = fallbackData.history;
      }

      set({
        sessions: newSessions,
        sessionData: newSessionData,
        activeSessionId: newActiveId,
        messages: newMessages,
        history: newHistory,
      });

      persist(
        get().sessions,
        get().sessionData,
        get().activeSessionId,
      );
    },

    renameSession: (sessionId, title) => {
      set((state) => ({
        sessions: state.sessions.map((s) =>
          s.id === sessionId ? { ...s, title, updatedAt: Date.now() } : s,
        ),
      }));

      persist(
        get().sessions,
        get().sessionData,
        get().activeSessionId,
      );
    },

    syncSessionTitle: () => {
      const state = get();
      if (!state.activeSessionId || state.messages.length === 0) return;

      // Auto-name session based on first user message
      const firstUserMsg = state.messages.find((m) => m.role === "user");
      if (!firstUserMsg) return;

      const session = state.sessions.find((s) => s.id === state.activeSessionId);
      if (!session || session.title !== "新对话") return;

      const title = firstUserMsg.content.length > 20
        ? firstUserMsg.content.slice(0, 20) + "…"
        : firstUserMsg.content;

      get().renameSession(state.activeSessionId, title);
    },

    addUserMessage: (content) => {
      const id = nextId();
      set((state) => ({
        messages: [
          ...state.messages,
          { id, role: "user" as const, content },
        ],
        history: [...state.history, { role: "user", content }],
      }));
    },

    addAssistantMessage: (id) => {
      set((state) => ({
        messages: [
          ...state.messages,
          {
            id,
            role: "assistant" as const,
            content: "",
            toolCalls: [],
            isStreaming: true,
          },
        ],
      }));
    },

    appendToAssistant: (id, text) => {
      if (!text) return;
      set((state) => ({
        messages: updateMessageById(state.messages, id, (message) => ({
          ...message,
          content: message.content + text,
        })),
      }));
    },

    addToolCall: (messageId, tc) => {
      const display: ToolCallDisplay = {
        id: tc.id,
        name: tc.function.name,
        arguments: tc.function.arguments,
        isExecuting: true,
      };
      set((state) => ({
        messages: updateMessageById(state.messages, messageId, (message) => ({
          ...message,
          toolCalls: [...(message.toolCalls || []), display],
        })),
        history: (() => {
          const hist = [...state.history];
          const lastIdx = hist.length - 1;
          if (
            lastIdx >= 0 &&
            hist[lastIdx].role === "assistant" &&
            hist[lastIdx].tool_calls
          ) {
            hist[lastIdx] = {
              ...hist[lastIdx],
              tool_calls: [...(hist[lastIdx].tool_calls || []), tc],
            };
          } else {
            hist.push({
              role: "assistant",
              content: null,
              tool_calls: [tc],
            });
          }
          return hist;
        })(),
      }));
    },

    updateToolResult: (messageId, toolCallId, result, isError) => {
      const displayResult =
        result.length > 500 ? `${result.slice(0, 500)}…` : result;
      set((state) => ({
        messages: updateMessageById(state.messages, messageId, (message) => ({
          ...message,
          toolCalls: (message.toolCalls || []).map((tc) =>
            tc.id === toolCallId
              ? { ...tc, result: displayResult, isError, isExecuting: false }
              : tc,
          ),
        })),
        history: [
          ...state.history,
          {
            role: "tool" as const,
            tool_call_id: toolCallId,
            content: result,
          },
        ],
      }));
    },

    setReasoningContent: (messageId, reasoningContent) => {
      set((state) => {
        const history = [...state.history];
        const assistantIdx = findLastAssistantIndex(history);

        if (assistantIdx >= 0) {
          history[assistantIdx] = {
            ...history[assistantIdx],
            reasoning_content: reasoningContent,
          };
        }

        return {
          history,
          messages: updateMessageById(state.messages, messageId, (message) => ({
            ...message,
            reasoningContent,
          })),
        };
      });
    },

    appendToReasoning: (messageId, text) => {
      if (!text) return;
      set((state) => ({
        messages: updateMessageById(state.messages, messageId, (message) => ({
          ...message,
          reasoningContent: (message.reasoningContent || "") + text,
        })),
      }));
    },

    setStreaming: (streaming) => set({ isStreaming: streaming }),
    setAbortController: (controller) => set({ abortController: controller }),

    clearChat: () => {
      set({
        messages: [],
        history: [],
        isStreaming: false,
        abortController: null,
      });
    },

    finalizeMessage: (messageId) =>
      set((state) => {
        const target = state.messages.find((m) => m.id === messageId);
        if (!target || target.isStreaming === false) return state;

        const history =
          target.role === "assistant" && target.content
            ? upsertAssistantHistory(
                state.history,
                target.content,
                target.reasoningContent,
              )
            : state.history;

        return {
          history,
          messages: updateMessageById(state.messages, messageId, (message) => ({
            ...message,
            isStreaming: false,
          })),
        };
      }),
  };
});
