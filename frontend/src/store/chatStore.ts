import { create } from "zustand";
import {
  createChatPersistSnapshot,
  flushChatPersist,
  scheduleChatPersist,
} from "./chatPersistence";
import { createChatMessageSlice } from "./chatMessageSlice";
import { createChatSessionSlice } from "./chatSessionSlice";
import { loadUserChatState } from "./chatStoreHelpers";
import type { ChatState } from "./chatStoreTypes";
import { getActiveUserScope, registerUserScopeHandler } from "./userScope";

export const useChatStore = create<ChatState>((set, get) => {
  const scopedState = loadUserChatState(window.localStorage, getActiveUserScope());
  const persist = () => {
    const state = get();
    scheduleChatPersist(
      window.localStorage,
      getActiveUserScope(),
      createChatPersistSnapshot(
        state.sessions,
        state.sessionData,
        state.activeSessionId,
        state.messages,
        state.history,
        state.agentNames,
        state.skillNames,
      ),
    );
  };

  if (typeof window !== "undefined") {
    window.addEventListener("beforeunload", flushChatPersist);
  }

  return {
    ...createChatSessionSlice(set, get, persist, scopedState),
    ...createChatMessageSlice(set, get, persist),
  };
});

registerUserScopeHandler((userId) => {
  flushChatPersist();
  useChatStore.getState().abortController?.abort();
  const scopedState = loadUserChatState(window.localStorage, userId);
  useChatStore.setState({
    messages: scopedState.messages,
    history: scopedState.history,
    agentNames: scopedState.agentNames,
    skillNames: scopedState.skillNames,
    isStreaming: false,
    abortController: null,
    sessions: scopedState.sessions,
    activeSessionId: scopedState.activeSessionId,
    sessionData: scopedState.sessionData,
  });
});
