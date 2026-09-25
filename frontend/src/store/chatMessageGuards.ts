import type { ChatDisplayMessage, ChatMessage, ToolCallDisplay, ReasoningBlock } from "../types/chat";

import { sanitizeProcessUpdates } from "../features/chat/chatProcess";

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

export function sanitizeReasoningBlocks(value: unknown, text: string): ReasoningBlock[] | undefined {
  if (!Array.isArray(value)) return undefined;
  const result: ReasoningBlock[] = [];
  let previousEnd = 0;
  for (const block of value) {
    if (!isRecord(block) || typeof block.block_id !== "string" || typeof block.source !== "string"
      || (block.stage !== "agent" && block.stage !== "synthesis")
      || typeof block.start !== "number" || !Number.isSafeInteger(block.start) || block.start < previousEnd
      || typeof block.end !== "number" || !Number.isSafeInteger(block.end) || block.end <= block.start || block.end > text.length
      || typeof block.turn !== "number" || !Number.isSafeInteger(block.turn) || block.turn < 1
      || typeof block.attempt !== "number" || !Number.isSafeInteger(block.attempt) || block.attempt < 1
      || !isOptionalString(block.task_id)) continue;
    result.push({ block_id: block.block_id, source: block.source, stage: block.stage,
      start: block.start, end: block.end, turn: block.turn, attempt: block.attempt,
      task_id: typeof block.task_id === "string" ? block.task_id : undefined });
    previousEnd = block.end;
  }
  return result.length ? result : undefined;
}

export function sanitizeDisplayMessages(value: unknown): ChatDisplayMessage[] {
  return Array.isArray(value) ? value.filter(isChatDisplayMessage).map((message) => ({
    ...message,
    reasoningBlocks: sanitizeReasoningBlocks(message.reasoningBlocks, message.reasoningContent ?? ""),
    processUpdates: sanitizeProcessUpdates(message.processUpdates),
    processOutcome: ["completed", "partial", "failed", "cancelled"].includes(message.processOutcome ?? "")
      ? message.processOutcome : undefined,
  })) : [];
}

export function sanitizeHistoryMessages(value: unknown): ChatMessage[] {
  return Array.isArray(value) ? value.filter(isChatMessage) : [];
}
