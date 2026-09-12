import { useEffect, useState } from "react";
import { getChatState, saveChatState } from "../api/chatSessions";
import { ApiError } from "../api/client";
import { useAuthStore } from "../store/authStore";
import { fromServerChatState, toServerChatState } from "../store/chatServerSync";
import { useChatStore } from "../store/chatStore";

export type ChatSyncStatus = "loading" | "synced" | "error";

export function useChatSessionSync(): ChatSyncStatus {
  const userId = useAuthStore((state) => state.user?.id);
  const [status, setStatus] = useState<ChatSyncStatus>("loading");
  const updateStatus = (next: ChatSyncStatus) => {
    setStatus(next);
    useChatStore.getState().setSyncStatus(next);
  };

  useEffect(() => {
    if (userId == null) return;
    const controller = new AbortController();
    let disposed = false;
    let saveTimer: number | undefined;
    let unsubscribe: (() => void) | undefined;
    let saveQueue: Promise<void> = Promise.resolve();
    let lastPersistedSnapshot: string | undefined;
    let currentRevision = 0;

    const hydrateRemoteState = (response: Awaited<ReturnType<typeof getChatState>>) => {
      if (!response.state) return false;
      currentRevision = response.state.revision;
      useChatStore.getState().hydrateSessions(fromServerChatState(response.state));
      lastPersistedSnapshot = JSON.stringify(toServerChatState(useChatStore.getState()));
      return true;
    };

    const persistSnapshot = (snapshot: ReturnType<typeof toServerChatState>) => {
      const serializedSnapshot = JSON.stringify(snapshot);
      if (serializedSnapshot === lastPersistedSnapshot) {
        return Promise.resolve();
      }
      const operation = saveQueue
        .catch(() => undefined)
        .then(async () => {
          if (serializedSnapshot === lastPersistedSnapshot) return;
          try {
            const response = await saveChatState(snapshot, currentRevision);
            if (response.state) currentRevision = response.state.revision;
          } catch (error) {
            if (!(error instanceof ApiError) || error.code !== "chat.state_conflict") throw error;
            const response = await getChatState(controller.signal);
            if (!disposed) hydrateRemoteState(response);
            return;
          }
          lastPersistedSnapshot = serializedSnapshot;
        });
      saveQueue = operation;
      return operation.then(() => {
        if (!disposed) updateStatus("synced");
      }).catch((error: unknown) => {
        if (!disposed) updateStatus("error");
        throw error;
      });
    };

    const persistCurrentState = () => persistSnapshot(toServerChatState(useChatStore.getState()));

    const start = async () => {
      updateStatus("loading");
      try {
        const response = await getChatState(controller.signal);
        if (disposed) return;
        if (useChatStore.getState().isStreaming) {
          currentRevision = response.state?.revision ?? 0;
          lastPersistedSnapshot = undefined;
          await persistCurrentState();
        } else if (!hydrateRemoteState(response)) {
          await persistCurrentState();
        }
        if (disposed) return;
        updateStatus("synced");
        unsubscribe = useChatStore.subscribe(() => {
          window.clearTimeout(saveTimer);
          saveTimer = window.setTimeout(() => {
            saveTimer = undefined;
            void persistCurrentState().catch(() => undefined);
          }, 1_000);
        });
      } catch {
        if (!disposed) updateStatus("error");
      }
    };

    void start();
    return () => {
      disposed = true;
      controller.abort();
      unsubscribe?.();
      const hasPendingSave = saveTimer !== undefined;
      window.clearTimeout(saveTimer);
      if (hasPendingSave && useAuthStore.getState().user?.id === userId) {
        void persistCurrentState().catch(() => undefined);
      }
    };
  }, [userId]);

  return status;
}
