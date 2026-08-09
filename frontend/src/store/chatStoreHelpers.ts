import type { ChatDisplayMessage, ChatMessage } from "../types/chat";
import { loadPersistedChat } from "./chatPersistence";
import type { PersistedChatState } from "./chatPersistence";

interface UserChatState extends PersistedChatState {
  messages: ChatDisplayMessage[];
  history: ChatMessage[];
  agentNames: string[] | null;
  skillNames: string[] | null;
}

export interface ChatRegenerationRequest {
  message: string;
  history: ChatMessage[];
}

interface PreparedChatRegeneration extends ChatRegenerationRequest {
  nextMessages: ChatDisplayMessage[];
  nextHistory: ChatMessage[];
}

let messageCounter = 0;

export function nextChatMessageId() {
  messageCounter += 1;
  return `msg-${messageCounter}`;
}

export function loadUserChatState(storage: Storage, userId: number | null): UserChatState {
  const persisted = loadPersistedChat(storage, userId);
  const sessions = [...persisted.sessions];
  const sessionData = { ...persisted.sessionData };
  let activeSessionId = persisted.activeSessionId;

  if (sessions.length === 0) {
    const now = Date.now();
    const id = `session-${now}`;
    sessions.push({ id, title: "新对话", createdAt: now, updatedAt: now });
    sessionData[id] = { messages: [], history: [], agentNames: null, skillNames: null };
    activeSessionId = id;
  } else if (!activeSessionId || !sessions.some((session) => session.id === activeSessionId)) {
    activeSessionId = sessions[0].id;
  }

  const activeData = sessionData[activeSessionId] ?? {
    messages: [],
    history: [],
    agentNames: null,
    skillNames: null,
  };
  sessionData[activeSessionId] = activeData;
  return {
    sessions,
    sessionData,
    activeSessionId,
    messages: activeData.messages,
    history: activeData.history,
    agentNames: activeData.agentNames ?? null,
    skillNames: activeData.skillNames ?? null,
  };
}

export function updateMessageById(
  messages: ChatDisplayMessage[],
  id: string,
  updater: (message: ChatDisplayMessage) => ChatDisplayMessage,
) {
  return messages.map((message) => message.id === id ? updater(message) : message);
}

export function prepareLastAssistantRegeneration(
  messages: ChatDisplayMessage[],
  history: ChatMessage[],
): PreparedChatRegeneration | null {
  const assistantMessage = messages[messages.length - 1];
  if (!assistantMessage || assistantMessage.role !== "assistant" || assistantMessage.isStreaming) {
    return null;
  }

  let userMessageIndex = messages.length - 2;
  while (userMessageIndex >= 0 && messages[userMessageIndex].role !== "user") {
    userMessageIndex -= 1;
  }
  if (userMessageIndex < 0) return null;

  const userMessage = messages[userMessageIndex];
  let historyUserIndex = history.length - 1;
  while (
    historyUserIndex >= 0
    && (
      history[historyUserIndex].role !== "user"
      || history[historyUserIndex].content !== userMessage.content
    )
  ) {
    historyUserIndex -= 1;
  }
  if (historyUserIndex < 0) return null;

  return {
    message: userMessage.content,
    history: history.slice(0, historyUserIndex),
    nextMessages: messages.slice(0, userMessageIndex + 1),
    nextHistory: history.slice(0, historyUserIndex + 1),
  };
}

function findLastAssistantIndex(history: ChatMessage[]) {
  for (let index = history.length - 1; index >= 0; index -= 1) {
    if (history[index].role === "assistant") return index;
  }
  return -1;
}

export function upsertAssistantHistory(history: ChatMessage[], content: string) {
  const nextHistory = history
    .filter((item) => item.role !== "tool")
    .map((item) => item.role === "assistant"
      ? { ...item, tool_calls: undefined, reasoning_content: undefined }
      : item);
  const assistantIndex = findLastAssistantIndex(nextHistory);

  if (assistantIndex >= 0) {
    nextHistory[assistantIndex] = {
      ...nextHistory[assistantIndex],
      content,
      reasoning_content: undefined,
      tool_calls: undefined,
    };
  } else {
    nextHistory.push({ role: "assistant", content });
  }

  return nextHistory;
}
