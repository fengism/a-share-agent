import { appendProcessUpdate, finalizeChatProcess } from "../features/chat/chatProcess";
import type { ToolCallDisplay } from "../types/chat";
import {
  nextChatMessageId,
  prepareLastAssistantRegeneration,
  prepareUserMessageEdit,
  updateMessageById,
  upsertAssistantHistory,
} from "./chatStoreHelpers";
import type { ChatState } from "./chatStoreTypes";
import type { ChatStoreGet, ChatStoreSet, PersistChatStore } from "./chatStoreSliceTypes";

type ChatMessageSlice = Pick<
  ChatState,
  | "isStreaming"
  | "activeRunSessionId"
  | "activeRunLabel"
  | "syncStatus"
  | "abortController"
  | "addUserMessage"
  | "addAssistantMessage"
  | "appendToAssistant"
  | "addToolCall"
  | "updateToolResult"
  | "setAssistantPlan"
  | "updateAssistantPlanStep"
  | "setReasoningContent"
  | "appendToReasoning"
  | "setAssistantStatus"
  | "addAssistantProcessUpdate"
  | "setAssistantProcessOutcome"
  | "setStreaming"
  | "setActiveRun"
  | "setSyncStatus"
  | "setAbortController"
  | "clearChat"
  | "regenerateLastAssistant"
  | "editUserMessage"
  | "finalizeMessage"
>;

export function createChatMessageSlice(
  set: ChatStoreSet,
  get: ChatStoreGet,
  persist: PersistChatStore,
): ChatMessageSlice {
  return {
    isStreaming: false,
    activeRunSessionId: null,
    activeRunLabel: null,
    syncStatus: "loading",
    abortController: null,

    addUserMessage: (content) => {
      const id = nextChatMessageId();
      set((state) => ({
        messages: [...state.messages, { id, role: "user" as const, content }],
        history: [...state.history, { role: "user", content }],
      }));
    },

    addAssistantMessage: (id) => {
      set((state) => ({
        messages: [
          ...state.messages,
          { id, role: "assistant" as const, content: "", toolCalls: [], isStreaming: true },
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

    addToolCall: (messageId, toolCall) => {
      const display: ToolCallDisplay = {
        id: toolCall.id,
        name: toolCall.function.name,
        arguments: toolCall.function.arguments,
        isExecuting: true,
      };
      set((state) => ({
        messages: updateMessageById(state.messages, messageId, (message) => ({
          ...message,
          toolCalls: [...(message.toolCalls || []), display],
        })),
        history: (() => {
          const history = [...state.history];
          const lastIndex = history.length - 1;
          if (
            lastIndex >= 0
            && history[lastIndex].role === "assistant"
            && history[lastIndex].tool_calls
          ) {
            history[lastIndex] = {
              ...history[lastIndex],
              tool_calls: [...(history[lastIndex].tool_calls || []), toolCall],
            };
          } else {
            history.push({ role: "assistant", content: null, tool_calls: [toolCall] });
          }
          return history;
        })(),
      }));
    },

    updateToolResult: (messageId, toolCallId, result, isError, resultSummary) => {
      const displayResult = result.length > 4000 ? `${result.slice(0, 4000)}…` : result;
      set((state) => ({
        messages: updateMessageById(state.messages, messageId, (message) => ({
          ...message,
          toolCalls: (message.toolCalls || []).map((toolCall) => (
            toolCall.id === toolCallId
              ? {
                  ...toolCall,
                  result: displayResult,
                  resultSummary,
                  isError: isError && resultSummary?.status !== "skipped",
                  isSkipped: resultSummary?.status === "skipped",
                  isExecuting: false,
                }
              : toolCall
          )),
        })),
        history: [
          ...state.history,
          { role: "tool" as const, tool_call_id: toolCallId, content: result },
        ],
      }));
    },

    setAssistantPlan: (messageId, plan) => {
      set((state) => ({
        messages: updateMessageById(state.messages, messageId, (message) => ({
          ...message,
          plan: { ...plan, steps: plan.steps.map((step) => ({ ...step })) },
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
              steps: message.plan.steps.map((step) => (
                step.id === update.step_id
                  ? {
                      ...step,
                      status: update.status,
                      detail: update.detail,
                      attempt: update.attempt,
                    }
                  : step
              )),
            },
          };
        }),
      }));
    },

    setReasoningContent: (messageId, reasoningContent) => {
      set((state) => ({
        messages: updateMessageById(state.messages, messageId, (message) => ({
          ...message,
          reasoningContent,
          reasoningBlocks: undefined,
        })),
      }));
    },

    appendToReasoning: (messageId, text, source) => {
      if (!text) return;
      set((state) => ({
        messages: updateMessageById(state.messages, messageId, (message) => {
          const start = message.reasoningContent?.length ?? 0;
          const blocks = [...(message.reasoningBlocks ?? [])];
          const last = blocks[blocks.length - 1];
          if (source) {
            if (last?.block_id === source.block_id && last.end === start) {
              blocks[blocks.length - 1] = { ...last, end: start + text.length };
            } else {
              blocks.push({ ...source, start, end: start + text.length });
            }
          }
          return {
            ...message,
            reasoningContent: (message.reasoningContent || "") + text,
            reasoningBlocks: blocks.length ? blocks : undefined,
          };
        }),
      }));
    },

    addAssistantProcessUpdate: (messageId, update) => {
      set((state) => ({
        messages: updateMessageById(state.messages, messageId, (message) => ({
          ...message,
          processUpdates: appendProcessUpdate(message.processUpdates, update),
        })),
      }));
    },

    setAssistantProcessOutcome: (messageId, outcome) => {
      set((state) => ({
        messages: updateMessageById(state.messages, messageId, (message) => ({
          ...message,
          processOutcome: outcome,
        })),
      }));
    },

    setAssistantStatus: (messageId, status) => {
      set((state) => ({
        messages: updateMessageById(state.messages, messageId, (message) => ({
          ...message,
          status: status || undefined,
          processUpdates: appendProcessUpdate(message.processUpdates, { type: "status", content: status }),
        })),
      }));
    },

    setStreaming: (isStreaming) => set({ isStreaming }),
    setActiveRun: (activeRunSessionId, activeRunLabel) => set({ activeRunSessionId, activeRunLabel }),
    setSyncStatus: (syncStatus) => set((state) => (
      state.syncStatus === syncStatus ? state : { syncStatus }
    )),
    setAbortController: (abortController) => set({ abortController }),

    clearChat: () => {
      set({
        messages: [],
        history: [],
        isStreaming: false,
        activeRunSessionId: null,
        activeRunLabel: null,
        syncStatus: "loading",
        abortController: null,
      });
      persist();
    },

    regenerateLastAssistant: () => {
      const state = get();
      if (state.isStreaming) return null;
      const prepared = prepareLastAssistantRegeneration(state.messages, state.history);
      if (!prepared) return null;
      set({ messages: prepared.nextMessages, history: prepared.nextHistory });
      persist();
      return { message: prepared.message, history: prepared.history };
    },

    editUserMessage: (messageId, content) => {
      const state = get();
      if (state.isStreaming) return null;
      const prepared = prepareUserMessageEdit(state.messages, state.history, messageId, content);
      if (!prepared) return null;
      set({ messages: prepared.nextMessages, history: prepared.nextHistory });
      persist();
      return { message: prepared.message, history: prepared.history };
    },

    finalizeMessage: (messageId, outcome) => {
      set((state) => {
        const target = state.messages.find((message) => message.id === messageId);
        if (!target || target.isStreaming === false) return state;
        const history = target.role === "assistant" && target.content
          ? upsertAssistantHistory(state.history, target.content)
          : state.history;
        return {
          history,
          messages: updateMessageById(state.messages, messageId, (message) => (
            finalizeChatProcess(message, outcome)
          )),
        };
      });
      persist();
    },
  };
}
