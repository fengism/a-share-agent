import { streamChat } from "../../api/chat";
import { useChatStore } from "../../store/chatStore";
import { registerUserScopeHandler } from "../../store/userScope";
import type { ChatMessage, ChatStreamDelta } from "../../types/chat";
import { formatChatCompletionNotice } from "../../pages/Chat/chatCompletion";
import { createStreamDeltaBatcher } from "../../pages/Chat/streamDeltaBatcher";

interface StartChatOptions {
  input: string;
  history: ChatMessage[];
}

interface ActiveChatRun {
  id: number;
  sessionId: string;
  assistantId: string;
  controller: AbortController;
  batcher: ReturnType<typeof createStreamDeltaBatcher>;
  stopRequested: boolean;
}

let nextRunId = 0;
let activeRun: ActiveChatRun | null = null;

function ownsRun(run: ActiveChatRun) {
  return activeRun?.id === run.id;
}

function finishRun(run: ActiveChatRun) {
  if (!ownsRun(run)) return;
  run.batcher.flush();
  useChatStore.getState().finalizeMessage(run.assistantId);
  activeRun = null;
  useChatStore.getState().setAbortController(null);
  useChatStore.getState().setActiveRun(null, null);
  useChatStore.getState().setStreaming(false);
}

export function startChatRuntime({ input, history }: StartChatOptions) {
  if (activeRun) return false;
  const store = useChatStore.getState();
  const sessionId = store.activeSessionId;
  if (!sessionId) return false;
  nextRunId += 1;
  const assistantId = `msg-${Date.now()}-${nextRunId}`;
  const batcher = createStreamDeltaBatcher(({ text, reasoning }) => {
    if (!activeRun || activeRun.assistantId !== assistantId) return;
    const currentStore = useChatStore.getState();
    if (reasoning) currentStore.appendToReasoning(assistantId, reasoning);
    if (text) currentStore.appendToAssistant(assistantId, text);
  });
  store.addAssistantMessage(assistantId);
  store.setActiveRun(sessionId, input.length > 24 ? `${input.slice(0, 24)}…` : input);
  const controller = streamChat(input, history, {
    onDelta: (delta: ChatStreamDelta) => {
      const run = activeRun;
      if (!run || run.assistantId !== assistantId) return;
      const currentStore = useChatStore.getState();
      switch (delta.type) {
        case "status":
          batcher.flush();
          currentStore.setAssistantStatus(assistantId, delta.content || "");
          break;
        case "plan":
          batcher.flush();
          if (delta.plan) currentStore.setAssistantPlan(assistantId, delta.plan);
          break;
        case "plan_step":
          batcher.flush();
          if (delta.plan_step) currentStore.updateAssistantPlanStep(assistantId, delta.plan_step);
          break;
        case "reasoning":
          batcher.enqueueReasoning(delta.content || "");
          break;
        case "text":
          batcher.enqueueText(delta.content || "");
          break;
        case "tool_call":
          batcher.flush();
          if (delta.tool_call) currentStore.addToolCall(assistantId, delta.tool_call);
          break;
        case "tool_result":
          batcher.flush();
          if (delta.tool_result) {
            currentStore.updateToolResult(
              assistantId,
              delta.tool_result.tool_call_id,
              delta.tool_result.content || "",
              delta.tool_result.is_error,
              delta.tool_result_summary || undefined,
            );
          }
          break;
        case "error":
          batcher.flush();
          currentStore.appendToAssistant(assistantId, `\n\n[错误] ${delta.error}`);
          break;
        case "done":
          batcher.flush();
          if (delta.reasoning_content) currentStore.setReasoningContent(assistantId, delta.reasoning_content);
          currentStore.appendToAssistant(assistantId, formatChatCompletionNotice(delta));
          break;
      }
    },
    onError: (error) => {
      const run = activeRun;
      if (!run || run.assistantId !== assistantId || run.stopRequested) return;
      batcher.flush();
      useChatStore.getState().appendToAssistant(assistantId, `\n\n[连接错误] ${error.message}`);
      finishRun(run);
    },
    onDone: () => {
      const run = activeRun;
      if (!run || run.assistantId !== assistantId) return;
      batcher.flush();
      finishRun(run);
    },
  }, {
    agentNames: store.agentNames === null ? undefined : store.agentNames,
    skillNames: store.skillNames === null ? undefined : store.skillNames,
  });
  const run: ActiveChatRun = {
    id: nextRunId,
    sessionId,
    assistantId,
    controller,
    batcher,
    stopRequested: false,
  };
  activeRun = run;
  store.setAbortController(controller);
  store.setStreaming(true);
  return true;
}

export function stopChatRuntime() {
  const run = activeRun;
  if (!run || run.stopRequested) return false;
  run.stopRequested = true;
  run.batcher.flush();
  run.controller.abort();
  finishRun(run);
  return true;
}

export function getActiveChatRun() {
  if (!activeRun) return null;
  return {
    sessionId: activeRun.sessionId,
    assistantId: activeRun.assistantId,
  };
}

registerUserScopeHandler(() => {
  if (!activeRun) return;
  activeRun.stopRequested = true;
  activeRun.batcher.flush();
  activeRun.controller.abort();
  activeRun = null;
});
