import type { components } from "./generated/schema";
import { apiGet, apiPut } from "./client";

export type ChatStateResponse = components["schemas"]["ChatStateResponse"];
export type ChatStateSnapshot = components["schemas"]["ChatStateSnapshot"];
export type ChatStateContent = Omit<ChatStateSnapshot, "revision">;

export function getChatState(signal?: AbortSignal) {
  return apiGet<ChatStateResponse>("/chat/sessions", undefined, { signal });
}

export function saveChatState(state: ChatStateContent, revision: number) {
  return apiPut<ChatStateResponse>("/chat/sessions", { ...state, revision });
}
