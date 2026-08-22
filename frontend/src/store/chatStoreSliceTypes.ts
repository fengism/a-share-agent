import type { StateCreator } from "zustand";
import type { ChatState } from "./chatStoreTypes";

export type ChatStoreSet = Parameters<StateCreator<ChatState>>[0];
export type ChatStoreGet = Parameters<StateCreator<ChatState>>[1];
export type PersistChatStore = () => void;
