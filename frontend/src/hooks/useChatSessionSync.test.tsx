import { act, renderHook, cleanup } from "@testing-library/react";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import { getChatState, saveChatState } from "../api/chatSessions";
import { ApiError } from "../api/client";
import { useAuthStore } from "../store/authStore";
import { useChatStore } from "../store/chatStore";
import { toServerChatState } from "../store/chatServerSync";
import { loadPersistedChat } from "../store/chatPersistence";
import { readPendingChat } from "../store/chatSyncRecovery";
import { setActiveUserScope } from "../store/userScope";
import { useChatSessionSync } from "./useChatSessionSync";

vi.mock("../api/chatSessions", () => ({ getChatState: vi.fn(), saveChatState: vi.fn() }));
const user = (id: number) => ({ id }) as NonNullable<ReturnType<typeof useAuthStore.getState>["user"]>;
const tick = async () => { await act(async () => { await vi.advanceTimersByTimeAsync(1100); }); };

beforeEach(() => {
  vi.useFakeTimers();
  vi.resetAllMocks();
  setActiveUserScope(null);
  window.localStorage.clear();
  useAuthStore.setState({ user: user(1) });
  setActiveUserScope(1);
});
afterEach(() => {
  cleanup();
  setActiveUserScope(null);
  vi.clearAllTimers();
  vi.useRealTimers();
});

it("keeps failed saves on refresh and retries against the same revision", async () => {
  const remote = { ...toServerChatState(useChatStore.getState()), revision: 4 };
  vi.mocked(getChatState).mockResolvedValue({ state: remote });
  vi.mocked(saveChatState).mockRejectedValue(new Error("offline"));
  const hook = renderHook(() => useChatSessionSync());
  await tick();
  act(() => { useChatStore.getState().addUserMessage("本地新内容"); });
  await tick();
  expect(hook.result.current).toBe("error");
  hook.unmount();
  const local = loadPersistedChat(window.localStorage, 1);
  expect(JSON.stringify(local)).toContain("本地新内容");
  expect(readPendingChat(window.localStorage, 1)).toEqual({ revision: 4 });
  useChatStore.getState().hydrateSessions(local);
  vi.mocked(saveChatState).mockImplementation(async (snapshot) => ({ state: { ...snapshot, revision: 5 } }));
  const reloaded = renderHook(() => useChatSessionSync());
  await tick();
  expect(useChatStore.getState().messages[0].content).toBe("本地新内容");
  expect(reloaded.result.current).toBe("synced");
  expect(readPendingChat(window.localStorage, 1)).toBeNull();
});

it("does not hydrate remote or blindly overwrite on a revision conflict", async () => {
  const remote = { ...toServerChatState(useChatStore.getState()), revision: 4 };
  vi.mocked(getChatState).mockResolvedValue({ state: remote });
  vi.mocked(saveChatState).mockRejectedValue(new ApiError(409, "/chat/sessions", "conflict", { code: "chat.state_conflict" }));
  const hook = renderHook(() => useChatSessionSync());
  await tick();
  act(() => { useChatStore.getState().addUserMessage("不能丢失"); });
  await tick();
  expect(hook.result.current).toBe("error");
  expect(useChatStore.getState().messages[0].content).toBe("不能丢失");
  hook.unmount();
  vi.mocked(getChatState).mockResolvedValue({ state: { ...remote, revision: 5 } });
  renderHook(() => useChatSessionSync());
  await tick();
  expect(saveChatState).toHaveBeenCalledTimes(1);
  expect(useChatStore.getState().messages[0].content).toBe("不能丢失");
});

it("does not acknowledge edits made during an in-flight save and isolates accounts", async () => {
  vi.mocked(getChatState).mockResolvedValue({ state: { ...toServerChatState(useChatStore.getState()), revision: 1 } });
  let resolveSave!: (value: Awaited<ReturnType<typeof saveChatState>>) => void;
  vi.mocked(saveChatState).mockImplementation(() => new Promise((resolve) => { resolveSave = resolve; }));
  renderHook(() => useChatSessionSync());
  await tick();
  act(() => { useChatStore.getState().addUserMessage("first"); });
  await tick();
  act(() => { useChatStore.getState().addUserMessage("second"); });
  await act(async () => { resolveSave({ state: { ...toServerChatState(useChatStore.getState()), revision: 2 } }); });
  expect(readPendingChat(window.localStorage, 1)).toEqual({ revision: 2 });
  expect(readPendingChat(window.localStorage, 2)).toBeNull();
  act(() => { useAuthStore.setState({ user: user(2) }); setActiveUserScope(2); });
  expect(window.localStorage.getItem("chat-sessions:user:1-data")).toContain("second");
  expect(useChatStore.getState().messages).toEqual([]);
  await act(async () => {});
});

it("retains edits made while the initial GET is pending", async () => {
  const remote = { ...toServerChatState(useChatStore.getState()), revision: 9 };
  let resolveGet!: (value: Awaited<ReturnType<typeof getChatState>>) => void;
  vi.mocked(getChatState).mockImplementation(() => new Promise((resolve) => { resolveGet = resolve; }));
  const hook = renderHook(() => useChatSessionSync());
  act(() => { useChatStore.getState().addUserMessage("加载期间发送"); });
  await act(async () => { resolveGet({ state: remote }); });
  expect(useChatStore.getState().messages[0].content).toBe("加载期间发送");
  expect(hook.result.current).toBe("error");
  expect(saveChatState).not.toHaveBeenCalled();
});

it("retries a failed initial GET on the next edit without overlapping loads", async () => {
  vi.mocked(getChatState).mockRejectedValueOnce(new Error("offline"));
  const hook = renderHook(() => useChatSessionSync());
  await tick();
  expect(hook.result.current).toBe("error");
  let resolveGet!: (value: Awaited<ReturnType<typeof getChatState>>) => void;
  vi.mocked(getChatState).mockImplementation(() => new Promise((resolve) => { resolveGet = resolve; }));
  vi.mocked(saveChatState).mockImplementation(async (snapshot) => ({ state: { ...snapshot, revision: 1 } }));
  act(() => { useChatStore.getState().addUserMessage("断网时发送"); });
  await tick();
  act(() => {
    window.dispatchEvent(new Event("online"));
    window.dispatchEvent(new Event("online"));
  });
  expect(getChatState).toHaveBeenCalledTimes(2);
  await act(async () => { resolveGet({ state: null }); });
  expect(saveChatState).toHaveBeenCalledTimes(1);
  expect(JSON.stringify(vi.mocked(saveChatState).mock.calls[0][0])).toContain("断网时发送");
  expect(hook.result.current).toBe("synced");
});

it("retries the initial load on reconnect even without a new edit", async () => {
  vi.mocked(getChatState).mockRejectedValueOnce(new Error("offline"));
  const hook = renderHook(() => useChatSessionSync());
  await tick();
  vi.mocked(getChatState).mockResolvedValue({ state: { ...toServerChatState(useChatStore.getState()), revision: 2 } });
  await act(async () => { window.dispatchEvent(new Event("online")); });
  expect(getChatState).toHaveBeenCalledTimes(2);
  expect(hook.result.current).toBe("synced");
});

it("never sends queued saves or applies in-flight acknowledgements after logout", async () => {
  vi.mocked(getChatState).mockResolvedValue({ state: { ...toServerChatState(useChatStore.getState()), revision: 1 } });
  let resolveSave!: (value: Awaited<ReturnType<typeof saveChatState>>) => void;
  vi.mocked(saveChatState).mockImplementation(() => new Promise((resolve) => { resolveSave = resolve; }));
  renderHook(() => useChatSessionSync());
  await tick();
  act(() => { useChatStore.getState().addUserMessage("private first"); });
  await tick();
  act(() => { useChatStore.getState().addUserMessage("private second"); });
  await tick(); // Queued behind the first PUT.
  const response = { state: { ...toServerChatState(useChatStore.getState()), revision: 2 } };
  act(() => { useAuthStore.setState({ user: null }); setActiveUserScope(null); });
  await act(async () => { resolveSave(response); });
  await tick();
  expect(saveChatState).toHaveBeenCalledTimes(1);
  expect(readPendingChat(window.localStorage, 1)).toEqual({ revision: 1 });
  expect(window.localStorage.getItem("chat-sessions:user:1-data")).toContain("private second");
  expect(useChatStore.getState().messages).toEqual([]);
});
