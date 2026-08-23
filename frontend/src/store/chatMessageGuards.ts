import type { ChatDisplayMessage, ChatMessage, ToolCallDisplay } from "../types/chat";

// Structural guards for data crossing trust boundaries (localStorage and the
// server snapshot API): a bad payload degrades to a filtered-out message
// instead of crashing the chat render tree.

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isOptionalString(value: unknown): boolean {
  return value === undefined || value === null || typeof value === "string";
}

function isDisplayRole(value: unknown): value is ChatDisplayMessage["role"] {
  return value === "user" || value === "assistant";
}

function isHistoryRole(value: unknown): value is ChatMessage["role"] {
  return value === "user" || value === "assistant" || value === "tool";
}

function isToolCallDisplay(value: unknown): value is ToolCallDisplay {
  return isRecord(value)
    && typeof value.id === "string"
    && typeof value.name === "string"
    && typeof value.arguments === "string"
    && isOptionalString(value.result);
}

export function isChatDisplayMessage(value: unknown): value is ChatDisplayMessage {
  if (!isRecord(value)) return false;
  if (typeof value.id !== "string" || !isDisplayRole(value.role)) return false;
  if (typeof value.content !== "string") return false;
  if (value.toolCalls !== undefined && value.toolCalls !== null) {
    if (!Array.isArray(value.toolCalls) || !value.toolCalls.every(isToolCallDisplay)) return false;
  }
  if (!isOptionalString(value.reasoningContent)) return false;
  if (!isOptionalString(value.status)) return false;
  if (value.isStreaming !== undefined && typeof value.isStreaming !== "boolean") return false;
  return true;
}

export function isChatMessage(value: unknown): value is ChatMessage {
  if (!isRecord(value)) return false;
  if (!isHistoryRole(value.role)) return false;
  if (typeof value.content !== "string" && value.content !== null) return false;
  if (!isOptionalString(value.tool_call_id) || !isOptionalString(value.name) || !isOptionalString(value.reasoning_content)) {
    return false;
  }
  return true;
}

export function sanitizeDisplayMessages(value: unknown): ChatDisplayMessage[] {
  return Array.isArray(value) ? value.filter(isChatDisplayMessage) : [];
}

export function sanitizeHistoryMessages(value: unknown): ChatMessage[] {
  return Array.isArray(value) ? value.filter(isChatMessage) : [];
}
