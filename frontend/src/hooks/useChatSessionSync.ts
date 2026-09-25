import { useEffect, useState } from "react";
import { getChatState, saveChatState } from "../api/chatSessions";
import { ApiError } from "../api/client";
import { useAuthStore } from "../store/authStore";
import { fromServerChatState, toServerChatState } from "../store/chatServerSync";
import { useChatStore } from "../store/chatStore";
import { createChatPersistSnapshot, flushChatPersist, scheduleChatPersist } from "../store/chatPersistence";
import { clearPendingChat, markPendingChat, readPendingChat } from "../store/chatSyncRecovery";

export type ChatSyncStatus = "loading" | "synced" | "error";

export function useChatSessionSync(): ChatSyncStatus {
  const userId = useAuthStore((state) => state.user?.id);
  const [status, setStatus] = useState<ChatSyncStatus>("loading");

  useEffect(() => {
    if (userId == null) return;
    const controller = new AbortController();
    let disposed = false;
    let hydrating = false;
    let ready = false;
    let starting = false;
    let conflicted = false;
    let saveTimer: number | undefined;
    let saveQueue: Promise<void> = Promise.resolve();
    let lastPersistedSnapshot: string | undefined;
    let currentRevision: number | null = null;
    let changedDuringLoad = false;
    const ownsStore = () => useAuthStore.getState().user?.id === userId;
    const updateStatus = (next: ChatSyncStatus) => {
      if (disposed || !ownsStore()) return;
      setStatus(next);
      useChatStore.getState().setSyncStatus(next);
    };
    const rememberLocal = () => {
      const state = useChatStore.getState();
      markPendingChat(window.localStorage, userId, currentRevision);
      scheduleChatPersist(window.localStorage, userId, createChatPersistSnapshot(
        state.sessions, state.sessionData, state.activeSessionId, state.messages,
        state.history, state.agentNames, state.skillNames,
      ));
    };
    const persistCurrentState = () => {
      saveQueue = saveQueue.catch(() => undefined).then(async () => {
        if (disposed || !ownsStore() || !ready || conflicted) return;
        try {
          const snapshot = toServerChatState(useChatStore.getState());
          const serialized = JSON.stringify(snapshot);
          if (serialized !== lastPersistedSnapshot) {
            const response = await saveChatState(snapshot, currentRevision ?? 0);
            if (disposed || !ownsStore()) return;
            currentRevision = response.state?.revision ?? currentRevision;
            lastPersistedSnapshot = serialized;
          }
          // Never acknowledge a newer local edit with an older in-flight save.
          if (serialized === JSON.stringify(toServerChatState(useChatStore.getState()))) {
            clearPendingChat(window.localStorage, userId);
            updateStatus("synced");
          } else {
            rememberLocal();
          }
        } catch (error) {
          if (disposed || !ownsStore()) return;
          if (error instanceof ApiError && error.code === "chat.state_conflict") {
            // Keep BOTH versions: no remote hydration and no blind revision retry.
            conflicted = true;
          }
          updateStatus("error");
        }
      });
      return saveQueue;
    };
    const unsubscribe = useChatStore.subscribe((state, previous) => {
      if (hydrating || disposed || !ownsStore()) return;
      if (state.sessions === previous.sessions && state.sessionData === previous.sessionData
        && state.activeSessionId === previous.activeSessionId && state.messages === previous.messages
        && state.history === previous.history && state.agentNames === previous.agentNames
        && state.skillNames === previous.skillNames) return;
      changedDuringLoad = true;
      try { rememberLocal(); } catch { updateStatus("error"); }
      window.clearTimeout(saveTimer);
      saveTimer = window.setTimeout(() => {
        saveTimer = undefined;
        if (ready) void persistCurrentState();
        else void start();
      }, 1_000);
    });
    const start = async () => {
      if (starting || disposed || !ownsStore() || ready) return;
      starting = true;
      updateStatus("loading");
      try {
        const pending = readPendingChat(window.localStorage, userId);
        currentRevision = pending?.revision ?? null;
        const response = await getChatState(controller.signal);
        if (disposed || !ownsStore()) return;
        const remoteRevision = response.state?.revision ?? 0;
        const hasLocalEdits = pending !== null || changedDuringLoad || useChatStore.getState().isStreaming;
        if (hasLocalEdits && response.state && currentRevision !== remoteRevision) {
          conflicted = true;
          ready = true;
          updateStatus("error");
          return;
        }
        currentRevision = remoteRevision;
        if (!hasLocalEdits && response.state) {
          hydrating = true;
          try { useChatStore.getState().hydrateSessions(fromServerChatState(response.state)); }
          finally { hydrating = false; }
          lastPersistedSnapshot = JSON.stringify(toServerChatState(useChatStore.getState()));
        } else {
          rememberLocal();
        }
        ready = true;
        await persistCurrentState();
      } catch {
        updateStatus("error");
      } finally {
        starting = false;
      }
    };
    const flushLocal = () => {
      if (!ownsStore()) return;
      try { flushChatPersist(); } catch { updateStatus("error"); }
    };
    window.addEventListener("beforeunload", flushLocal);
    // An initial GET failure must not permanently disable synchronization.
    const retryOnline = () => { if (!ready) void start(); else void persistCurrentState(); };
    window.addEventListener("online", retryOnline);
    void start();
    return () => {
      flushLocal();
      disposed = true;
      controller.abort();
      unsubscribe();
      window.clearTimeout(saveTimer);
      window.removeEventListener("beforeunload", flushLocal);
      window.removeEventListener("online", retryOnline);
    };
  }, [userId]);

  return status;
}
