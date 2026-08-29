import { useCallback } from "react";
import { startChatRuntime, stopChatRuntime } from "../../features/chat/chatRuntime";
import { useChatStore } from "../../store/chatStore";

interface UseChatControllerOptions {
  inputValue: string;
  setInputValue: (value: string) => void;
}

export function useChatController({ inputValue, setInputValue }: UseChatControllerOptions) {
  const isStreaming = useChatStore((state) => state.isStreaming);
  const clearChat = useChatStore((state) => state.clearChat);
  const createSession = useChatStore((state) => state.createSession);
  const setActiveSession = useChatStore((state) => state.setActiveSession);
  const deleteSession = useChatStore((state) => state.deleteSession);

  const handleNewSession = useCallback(() => {
    if (isStreaming) return;
    createSession();
  }, [createSession, isStreaming]);

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
    startChatRuntime({ input, history });
  }, [inputValue, isStreaming, setInputValue]);

  const handleRegenerate = useCallback(() => {
    if (isStreaming) return;
    const request = useChatStore.getState().regenerateLastAssistant();
    if (request) startChatRuntime({ input: request.message, history: request.history });
  }, [isStreaming]);

  const handleClear = useCallback(() => {
    stopChatRuntime();
    clearChat();
  }, [clearChat]);

  const handleStop = useCallback(() => {
    stopChatRuntime();
  }, []);

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
