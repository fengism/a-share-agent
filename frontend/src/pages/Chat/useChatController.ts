import { useCallback, useEffect, useRef } from "react";
import { streamChat } from "../../api/chat";
import { useChatStore } from "../../store/chatStore";
import type { ChatStreamDelta } from "../../types/chat";
import { formatChatCompletionNotice } from "./chatCompletion";
import { createStreamDeltaBatcher, type StreamDeltaBatcher } from "./streamDeltaBatcher";

interface UseChatControllerOptions {
  inputValue: string;
  setInputValue: (value: string) => void;
}

export function useChatController({ inputValue, setInputValue }: UseChatControllerOptions) {
  const activeAssistantIdRef = useRef<string | null>(null);
  const activeControllerRef = useRef<AbortController | null>(null);
  const streamBatcherRef = useRef<StreamDeltaBatcher | null>(null);
  if (!streamBatcherRef.current) {
    streamBatcherRef.current = createStreamDeltaBatcher(({ text, reasoning }) => {
      const assistantId = activeAssistantIdRef.current;
      if (!assistantId) return;
      const store = useChatStore.getState();
      if (reasoning) store.appendToReasoning(assistantId, reasoning);
      if (text) store.appendToAssistant(assistantId, text);
    });
  }
  const streamBatcher = streamBatcherRef.current;
  const isStreaming = useChatStore((state) => state.isStreaming);
  const abortController = useChatStore((state) => state.abortController);
  const setStreaming = useChatStore((state) => state.setStreaming);
  const setAbortController = useChatStore((state) => state.setAbortController);
  const clearChat = useChatStore((state) => state.clearChat);
  const finalizeMessage = useChatStore((state) => state.finalizeMessage);
  const createSession = useChatStore((state) => state.createSession);
  const setActiveSession = useChatStore((state) => state.setActiveSession);
  const deleteSession = useChatStore((state) => state.deleteSession);

  const clearActiveRequest = useCallback(() => {
    streamBatcher.flush();
    activeControllerRef.current = null;
    activeAssistantIdRef.current = null;
    setAbortController(null);
    setStreaming(false);
  }, [setAbortController, setStreaming, streamBatcher]);

  useEffect(
    () => () => {
      streamBatcher.flush();
      activeControllerRef.current?.abort();
      activeAssistantIdRef.current = null;
      setAbortController(null);
      setStreaming(false);
    },
    [setAbortController, setStreaming, streamBatcher],
  );

  const startAssistantStream = useCallback((
    input: string,
    history: ReturnType<typeof useChatStore.getState>["history"],
  ) => {
    const store = useChatStore.getState();
    streamBatcher.flush();
    const assistantId = `msg-${Date.now()}`;
    activeAssistantIdRef.current = assistantId;
    store.addAssistantMessage(assistantId);

    const controller = streamChat(input, history, {
      onDelta: (delta: ChatStreamDelta) => {
        const currentStore = useChatStore.getState();
        switch (delta.type) {
          case "status":
            streamBatcher.flush();
            currentStore.setAssistantStatus(assistantId, delta.content || "");
            break;
          case "plan":
            streamBatcher.flush();
            if (delta.plan) currentStore.setAssistantPlan(assistantId, delta.plan);
            break;
          case "plan_step":
            streamBatcher.flush();
            if (delta.plan_step) currentStore.updateAssistantPlanStep(assistantId, delta.plan_step);
            break;
          case "reasoning":
            streamBatcher.enqueueReasoning(delta.content || "");
            break;
          case "text":
            streamBatcher.enqueueText(delta.content || "");
            break;
          case "tool_call":
            streamBatcher.flush();
            if (delta.tool_call) currentStore.addToolCall(assistantId, delta.tool_call);
            break;
          case "tool_result":
            streamBatcher.flush();
            if (delta.tool_result) {
              currentStore.updateToolResult(
                assistantId,
                delta.tool_result.tool_call_id,
                delta.tool_result.content || "",
                delta.tool_result.is_error,
              );
            }
            break;
          case "error":
            streamBatcher.flush();
            currentStore.appendToAssistant(assistantId, `\n\n[错误] ${delta.error}`);
            break;
          case "done":
            streamBatcher.flush();
            if (delta.reasoning_content) {
              currentStore.setReasoningContent(assistantId, delta.reasoning_content);
            }
            currentStore.appendToAssistant(
              assistantId,
              formatChatCompletionNotice(delta),
            );
            currentStore.finalizeMessage(assistantId);
            break;
        }
      },
      onError: (error) => {
        streamBatcher.flush();
        const currentStore = useChatStore.getState();
        currentStore.appendToAssistant(assistantId, `\n\n[连接错误] ${error.message}`);
        currentStore.finalizeMessage(assistantId);
        clearActiveRequest();
      },
      onDone: () => {
        useChatStore.getState().finalizeMessage(assistantId);
        clearActiveRequest();
      },
    }, {
      agentNames: store.agentNames === null ? undefined : store.agentNames,
      skillNames: store.skillNames === null ? undefined : store.skillNames,
    });

    activeControllerRef.current = controller;
    store.setAbortController(controller);
    store.setStreaming(true);
  }, [clearActiveRequest, streamBatcher]);

  const handleNewSession = useCallback(() => {
    streamBatcher.flush();
    abortController?.abort();
    if (activeAssistantIdRef.current) finalizeMessage(activeAssistantIdRef.current);
    clearActiveRequest();
    createSession();
  }, [abortController, clearActiveRequest, createSession, finalizeMessage, streamBatcher]);

  const handleSessionClick = useCallback((sessionId: string) => {
    if (!isStreaming) setActiveSession(sessionId);
  }, [isStreaming, setActiveSession]);

  const handleDeleteSession = useCallback((sessionId: string) => {
    if (!isStreaming) deleteSession(sessionId);
  }, [deleteSession, isStreaming]);

  const handleSend = useCallback(() => {
    const input = inputValue.trim();
    if (!input || isStreaming) return;
    const store = useChatStore.getState();
    const history = store.history;
    setInputValue("");
    store.addUserMessage(input);
    store.syncSessionTitle();
    startAssistantStream(input, history);
  }, [inputValue, isStreaming, setInputValue, startAssistantStream]);

  const handleRegenerate = useCallback(() => {
    if (isStreaming) return;
    streamBatcher.flush();
    const request = useChatStore.getState().regenerateLastAssistant();
    if (request) startAssistantStream(request.message, request.history);
  }, [isStreaming, startAssistantStream, streamBatcher]);

  const handleClear = useCallback(() => {
    streamBatcher.flush();
    abortController?.abort();
    activeControllerRef.current = null;
    activeAssistantIdRef.current = null;
    clearChat();
  }, [abortController, clearChat, streamBatcher]);

  const handleStop = useCallback(() => {
    streamBatcher.flush();
    abortController?.abort();
    if (activeAssistantIdRef.current) finalizeMessage(activeAssistantIdRef.current);
    clearActiveRequest();
  }, [abortController, clearActiveRequest, finalizeMessage, streamBatcher]);

  return {
    isStreaming,
    handleClear,
    handleDeleteSession,
    handleNewSession,
    handleRegenerate,
    handleSend,
    handleSessionClick,
    handleStop,
  };
}
