import type { ChatMessage, ChatStreamDelta } from "../types/chat";
import { getCsrfToken, getToken, notifyUnauthorized } from "./authToken";
import { parseApiError } from "./errors";

const BASE_URL = "/api";
const MAX_REQUEST_HISTORY_MESSAGES = 20;
const MAX_REQUEST_HISTORY_CHARACTERS = 40_000;
const MAX_REQUEST_USER_MESSAGE_CHARACTERS = 10_000;

export function prepareChatHistory(
  history: ChatMessage[] | undefined,
  currentMessage: string,
): ChatMessage[] | undefined {
  const compact = (history || [])
    .filter((item) => item.role === "user" || item.role === "assistant")
    .map((item) => ({ role: item.role as "user" | "assistant", content: item.content?.trim() || "" }))
    .filter((item) => item.content);

  const lastItem = compact[compact.length - 1];
  if (lastItem?.role === "user" && lastItem.content === currentMessage) {
    compact.pop();
  }

  const selected: ChatMessage[] = [];
  let totalCharacters = 0;
  for (let index = compact.length - 1; index >= 0; index -= 1) {
    if (selected.length >= MAX_REQUEST_HISTORY_MESSAGES) break;
    const item = compact[index];
    if (!item) continue;
    const remaining = MAX_REQUEST_HISTORY_CHARACTERS - totalCharacters;
    if (remaining <= 0) break;
    const itemLimit = selected.length === 0 && item.role === "assistant"
      ? Math.max(0, remaining - MAX_REQUEST_USER_MESSAGE_CHARACTERS)
      : remaining;
    const content = item.content.length > itemLimit
      ? item.content.slice(-itemLimit)
      : item.content;
    if (!content) continue;
    selected.push({ role: item.role, content });
    totalCharacters += content.length;
  }
  selected.reverse();
  while (selected[0]?.role === "assistant") selected.shift();
  return selected.length ? selected : undefined;
}

export interface ChatStreamCallbacks {
  onDelta: (delta: ChatStreamDelta) => void;
  onError: (error: Error) => void;
  onDone: () => void;
}

export interface ChatRequestOptions {
  agentNames?: string[];
  skillNames?: string[];
}

export function buildChatRequestPayload(
  message: string,
  history: ChatMessage[] | undefined,
  options?: ChatRequestOptions,
) {
  return {
    message,
    history: prepareChatHistory(history, message),
    ...(options?.agentNames !== undefined ? { agent_names: options.agentNames } : {}),
    ...(options?.skillNames !== undefined ? { skill_names: options.skillNames } : {}),
  };
}

export function streamChat(
  message: string,
  history: ChatMessage[] | undefined,
  callbacks: ChatStreamCallbacks,
  options?: ChatRequestOptions,
): AbortController {
  const controller = new AbortController();

  const body = JSON.stringify(buildChatRequestPayload(message, history, options));

  const token = getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const csrfToken = getCsrfToken();
  if (csrfToken) headers["X-CSRF-Token"] = csrfToken;

  fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers,
    body,
    signal: controller.signal,
    credentials: "include",
  })
    .then(async (response) => {
      if (!response.ok) {
        if (response.status === 401) notifyUnauthorized();
        const error = parseApiError(
          await response.json().catch(() => ({})),
          `Chat API error: ${response.status}`,
        );
        throw new Error(error.message);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";
      let receivedTerminalEvent = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith("data: ")) continue;
          const jsonStr = trimmed.slice(6);
          try {
            const delta: ChatStreamDelta = JSON.parse(jsonStr);
            if (delta.type === "done" || delta.type === "error") {
              receivedTerminalEvent = true;
            }
            callbacks.onDelta(delta);
          } catch {
            // skip malformed JSON
          }
        }
      }
      if (!receivedTerminalEvent) {
        throw new Error("Chat 连接提前中断，请重试");
      }
      callbacks.onDone();
    })
    .catch((err) => {
      if (err.name === "AbortError") return;
      callbacks.onError(err instanceof Error ? err : new Error(String(err)));
    });

  return controller;
}
