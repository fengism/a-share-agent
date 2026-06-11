import { create } from "zustand";
import type {
  ChatDisplayMessage,
  ChatMessage,
  ToolCallDisplay,
  ToolCallInfo,
} from "../types/chat";

interface ChatState {
  messages: ChatDisplayMessage[];
  history: ChatMessage[];
  isStreaming: boolean;
  abortController: AbortController | null;

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

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  history: [],
  isStreaming: false,
  abortController: null,

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
    // 展示用截断到 500 字符避免 UI 过长，历史保留完整内容回传给后端
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
  clearChat: () =>
    set({
      messages: [],
      history: [],
      isStreaming: false,
      abortController: null,
    }),

  finalizeMessage: (messageId) =>
    set((state) => {
      const target = state.messages.find((m) => m.id === messageId);
      if (!target || target.isStreaming === false) {
        return state;
      }

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
}));
