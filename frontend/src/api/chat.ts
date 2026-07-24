import type { ChatMessage, ChatStreamDelta } from "../types/chat";
import { getToken, notifyUnauthorized } from "./authToken";

const BASE_URL = "/api";

export interface ChatStreamCallbacks {
  onDelta: (delta: ChatStreamDelta) => void;
  onError: (error: Error) => void;
  onDone: () => void;
}

export function streamChat(
  message: string,
  history: ChatMessage[] | undefined,
  callbacks: ChatStreamCallbacks,
): AbortController {
  const controller = new AbortController();

  const body = JSON.stringify({
    message,
    history: history?.length ? history : undefined,
  });

  const token = getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers,
    body,
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        if (response.status === 401 && token) notifyUnauthorized();
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Chat API error: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";

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
            callbacks.onDelta(delta);
          } catch {
            // skip malformed JSON
          }
        }
      }
      callbacks.onDone();
    })
    .catch((err) => {
      if (err.name === "AbortError") return;
      callbacks.onError(err instanceof Error ? err : new Error(String(err)));
    });

  return controller;
}
