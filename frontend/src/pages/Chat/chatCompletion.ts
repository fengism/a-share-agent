import type { AgentExecutionStatus } from "../../types/chat";

interface ChatCompletionOutcome {
  status?: AgentExecutionStatus | null;
  warnings?: string[];
}

export function formatChatCompletionNotice(outcome: ChatCompletionOutcome): string {
  const warnings = Array.from(new Set(
    (outcome.warnings || []).map((warning) => warning.trim()).filter(Boolean),
  ));
  if (!warnings.length && outcome.status === "partial") {
    warnings.push("回答仅部分完成，请结合工具和步骤状态谨慎参考");
  }
  return warnings.map((warning) => `\n\n[提示] ${warning}`).join("");
}
