import type { ChatDisplayMessage, ChatProcessOutcome, ChatResearchRound, ChatProcessUpdate } from "../../types/chat";

export const MAX_PROCESS_UPDATES = 60;
const MAX_TEXT_LENGTH = 2000;
const ROUND_TEXT_FIELDS = ["objective", "tool_selection_reason", "conclusion", "next_step"] as const;
const ROUND_LIST_FIELDS = ["evidence_gaps", "tool_names", "evidence_added", "judgment_basis"] as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

// Only public execution metadata belongs here, never raw reasoning/text/tool payloads.
export function normalizeProcessUpdate(value: unknown): ChatProcessUpdate | undefined {
  if (!isRecord(value)) return undefined;
  if (value.type === "status" && typeof value.content === "string") {
    const content = value.content.trim().slice(0, MAX_TEXT_LENGTH);
    return content ? { type: "status", content } : undefined;
  }
  if (value.type !== "round" || !isRecord(value.round)) return undefined;
  const round = value.round;
  if (!Number.isInteger(round.round_index) || Number(round.round_index) < 1
    || !Number.isInteger(round.round_total) || Number(round.round_total) < 1
    || !["running", "completed", "degraded", "cancelled", "failed"].includes(String(round.status))
    || !ROUND_TEXT_FIELDS.every((key) => typeof round[key] === "string")
    || !ROUND_LIST_FIELDS.every((key) => Array.isArray(round[key])
      && round[key].every((item: unknown) => typeof item === "string"))) return undefined;
  return {
    type: "round",
    round: {
      round_index: Number(round.round_index),
      round_total: Number(round.round_total),
      status: round.status as ChatResearchRound["status"],
      ...Object.fromEntries(ROUND_TEXT_FIELDS.map((key) => [key, (round[key] as string).slice(0, MAX_TEXT_LENGTH)])),
      ...Object.fromEntries(ROUND_LIST_FIELDS.map((key) => [key, (round[key] as string[]).slice(0, 12).map((text) => text.slice(0, MAX_TEXT_LENGTH))])),
    } as ChatResearchRound,
  };
}

export function appendProcessUpdate(
  updates: ChatProcessUpdate[] = [],
  value: unknown,
): ChatProcessUpdate[] {
  const update = normalizeProcessUpdate(value);
  if (!update) return updates;
  const last = updates[updates.length - 1];
  if (update.type === "status" && last?.type === "status" && last.content === update.content) return updates;
  if (update.type === "round") {
    const index = updates.findIndex((item) => item.type === "round" && item.round.round_index === update.round.round_index);
    if (index >= 0) return updates.map((item, i) => i === index ? update : item);
  }
  return [...updates, update].slice(-MAX_PROCESS_UPDATES);
}

export function sanitizeProcessUpdates(value: unknown): ChatProcessUpdate[] | undefined {
  if (!Array.isArray(value)) return undefined;
  return value.slice(-MAX_PROCESS_UPDATES).reduce<ChatProcessUpdate[]>(appendProcessUpdate, []);
}

/** Settle every live indicator together, preserving completed work and evidence. */
export function finalizeChatProcess(
  message: ChatDisplayMessage,
  outcome?: ChatProcessOutcome,
): ChatDisplayMessage {
  const processOutcome = outcome === "cancelled" ? outcome : message.processOutcome ?? outcome;
  const failed = processOutcome === "failed";
  const status = failed ? "failed" : "cancelled";
  return {
    ...message,
    isStreaming: false,
    processOutcome,
    status: undefined,
    plan: message.plan && Array.isArray(message.plan.steps)
      ? {
          ...message.plan,
          steps: message.plan.steps.map((step) => (
            step.status === "pending" || step.status === "running"
              ? { ...step, status, detail: failed ? "执行失败，流程已结束" : "执行已停止" }
              : step
          )),
        }
      : undefined,
    toolCalls: message.toolCalls?.map((tool) => tool.isExecuting
      ? { ...tool, isExecuting: false, isCancelled: !failed, isError: failed }
      : tool),
    processUpdates: message.processUpdates?.map((update) => (
      update.type === "round" && update.round.status === "running"
        ? { ...update, round: { ...update.round, status } }
        : update
    )),
  };
}

/** A saved snapshot has no live transport to resume, even if its flags say so. */
export function restoreChatProcess(message: ChatDisplayMessage): ChatDisplayMessage {
  if (message.role !== "assistant") return message;
  const hasUnfinishedWork = message.isStreaming || message.status
    || message.toolCalls?.some((tool) => tool.isExecuting)
    || (Array.isArray(message.plan?.steps) && message.plan.steps.some((step) => (
      step.status === "running" || step.status === "pending"
    )))
    || message.processUpdates?.some((update) => update.type === "round" && update.round.status === "running");
  return hasUnfinishedWork
    ? finalizeChatProcess(message, message.processOutcome ?? "cancelled")
    : message;
}
