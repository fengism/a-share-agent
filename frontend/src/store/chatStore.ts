import { create } from "zustand";
import type { ToolCallDisplay } from "../types/chat";
import {
  getActiveUserScope,
  registerUserScopeHandler,
} from "./userScope";
import {
  createChatPersistSnapshot,
  flushChatPersist,
  scheduleChatPersist,
} from "./chatPersistence";
import type { SessionMeta } from "./chatPersistence";
import {
  loadUserChatState,
  nextChatMessageId,
  prepareLastAssistantRegeneration,
  updateMessageById,
  upsertAssistantHistory,
} from "./chatStoreHelpers";
import type { ChatState } from "./chatStoreTypes";

export const useChatStore = create<ChatState>((set, get) => {
  const scopedState = loadUserChatState(window.localStorage, getActiveUserScope());

  const persist = () => {
    const state = get();
    scheduleChatPersist(
      window.localStorage,
      getActiveUserScope(),
      createChatPersistSnapshot(
        state.sessions,
        state.sessionData,
        state.activeSessionId,
        state.messages,
        state.history,
        state.agentNames,
        state.skillNames,
      ),
    );
  };

  // Flush pending localStorage writes on page unload
  if (typeof window !== "undefined") {
    window.addEventListener("beforeunload", flushChatPersist);
  }

  return {
    // Active session
    messages: scopedState.messages,
    history: scopedState.history,
    agentNames: scopedState.agentNames,
    skillNames: scopedState.skillNames,
    isStreaming: false,
    abortController: null,

    // Session management
    sessions: scopedState.sessions,
    activeSessionId: scopedState.activeSessionId,
    sessionData: scopedState.sessionData,

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
        id, title: "新对话", createdAt: Date.now(), updatedAt: Date.now(),
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

      // Load new session data
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
      if (state.sessions.length <= 1) return; // Keep at least one session

      const newSessions = state.sessions.filter((s) => s.id !== sessionId);
      const newSessionData = { ...state.sessionData };
      delete newSessionData[sessionId];

      let newActiveId = state.activeSessionId;
      let newMessages = state.messages;
      let newHistory = state.history;
      let newAgentNames = state.agentNames;
      let newSkillNames = state.skillNames;

      if (sessionId === state.activeSessionId) {
        // Switch to another session
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
        sessions: state.sessions.map((s) =>
          s.id === sessionId ? { ...s, title, updatedAt: Date.now() } : s,
        ),
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
      const id = nextChatMessageId();
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
          status: undefined,
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
        result.length > 4000 ? `${result.slice(0, 4000)}…` : result;
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

    setAssistantPlan: (messageId, plan) => {
      set((state) => ({
        messages: updateMessageById(state.messages, messageId, (message) => ({
          ...message,
          plan: {
            ...plan,
            steps: plan.steps.map((step) => ({ ...step })),
          },
        })),
      }));
    },

    updateAssistantPlanStep: (messageId, update) => {
      set((state) => ({
        messages: updateMessageById(state.messages, messageId, (message) => {
          if (!message.plan) return message;
          return {
            ...message,
            plan: {
              ...message.plan,
              steps: message.plan.steps.map((step) =>
                step.id === update.step_id
                  ? {
                      ...step,
                      status: update.status,
                      detail: update.detail,
                      attempt: update.attempt,
                    }
                  : step,
              ),
            },
          };
        }),
      }));
    },

    setReasoningContent: (messageId, reasoningContent) => {
      set((state) => {
        return {
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

    setAssistantStatus: (messageId, status) => {
      set((state) => ({
        messages: updateMessageById(state.messages, messageId, (message) => ({
          ...message,
          status: status || undefined,
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
      persist();
    },

    regenerateLastAssistant: () => {
      const state = get();
      if (state.isStreaming) return null;
      const prepared = prepareLastAssistantRegeneration(state.messages, state.history);
      if (!prepared) return null;

      set({
        messages: prepared.nextMessages,
        history: prepared.nextHistory,
      });
      persist();
      return {
        message: prepared.message,
        history: prepared.history,
      };
    },

    finalizeMessage: (messageId) => {
      set((state) => {
        const target = state.messages.find((m) => m.id === messageId);
        if (!target || target.isStreaming === false) return state;

        const history =
          target.role === "assistant" && target.content
            ? upsertAssistantHistory(
                state.history,
                target.content,
              )
            : state.history;

        return {
          history,
          messages: updateMessageById(state.messages, messageId, (message) => ({
            ...message,
            isStreaming: false,
            status: undefined,
            plan: message.plan
              ? {
                  ...message.plan,
                  steps: message.plan.steps.map((step) =>
                    step.status === "pending" || step.status === "running"
                      ? { ...step, status: "cancelled", detail: "执行已停止" }
                      : step,
                  ),
                }
              : undefined,
            toolCalls: message.toolCalls?.map((toolCall) =>
              toolCall.isExecuting
                ? { ...toolCall, isExecuting: false, isCancelled: true }
                : toolCall,
            ),
          })),
        };
      });
      persist();
    },
  };
});

registerUserScopeHandler((userId) => {
  flushChatPersist();
  useChatStore.getState().abortController?.abort();
  const scopedState = loadUserChatState(window.localStorage, userId);
  useChatStore.setState({
    messages: scopedState.messages,
    history: scopedState.history,
    agentNames: scopedState.agentNames,
    skillNames: scopedState.skillNames,
    isStreaming: false,
    abortController: null,
    sessions: scopedState.sessions,
    activeSessionId: scopedState.activeSessionId,
    sessionData: scopedState.sessionData,
  });
});
