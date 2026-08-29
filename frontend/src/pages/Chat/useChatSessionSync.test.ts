import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../api/client";
import { useAuthStore } from "../../store/authStore";
import { useChatStore } from "../../store/chatStore";
import { useChatSessionSync } from "./useChatSessionSync";

const mocks = vi.hoisted(() => ({
  getChatState: vi.fn(),
  saveChatState: vi.fn(),
}));

vi.mock("../../api/chatSessions", () => ({
  getChatState: mocks.getChatState,
  saveChatState: mocks.saveChatState,
}));

const remoteState = {
  revision: 2,
  sessions: [{ id: "remote-session", title: "远端会话", created_at: 1, updated_at: 2 }],
  session_data: {
    "remote-session": {
      messages: [{ id: "remote-message", role: "user", content: "远端内容" }],
      history: [{ role: "user" as const, content: "远端内容" }],
      agent_names: null,
      skill_names: null,
    },
  },
  active_session_id: "remote-session",
};

describe("useChatSessionSync", () => {
  beforeEach(() => {
    useChatStore.getState().abortController?.abort();
    useChatStore.setState({ isStreaming: false, activeRunSessionId: null, activeRunLabel: null, abortController: null });
    mocks.getChatState.mockReset().mockResolvedValue({ state: remoteState, updated_at: 2 });
    mocks.saveChatState.mockReset().mockResolvedValue({
      state: { ...remoteState, revision: 3 },
      updated_at: 3,
    });
    useAuthStore.setState({
      user: { id: 7, username: "tester", is_admin: false, must_change_password: false },
      bootstrapped: true,
    });
  });

  afterEach(() => {
    useAuthStore.setState({ user: null });
  });

  it("hydrates remote sessions and debounces subsequent writes", async () => {
    const { result, unmount } = renderHook(() => useChatSessionSync());

    await waitFor(() => expect(result.current).toBe("synced"));
    expect(useChatStore.getState().activeSessionId).toBe("remote-session");
    expect(useChatStore.getState().messages[0]?.content).toBe("远端内容");

    act(() => useChatStore.getState().renameSession("remote-session", "更新后的会话"));
    await waitFor(() => expect(mocks.saveChatState).toHaveBeenCalledOnce(), { timeout: 2_000 });
    expect(mocks.saveChatState.mock.calls[0][0].sessions[0].title).toBe("更新后的会话");
    expect(mocks.saveChatState.mock.calls[0][1]).toBe(2);
    unmount();
  });

  it("skips PUT when only non-persisted chat state changes", async () => {
    const { result, unmount } = renderHook(() => useChatSessionSync());
    await waitFor(() => expect(result.current).toBe("synced"));
    mocks.saveChatState.mockClear();
    vi.useFakeTimers();
    try {
      act(() => useChatStore.getState().setStreaming(true));
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1_000);
      });

      expect(mocks.saveChatState).not.toHaveBeenCalled();
      unmount();
    } finally {
      vi.useRealTimers();
    }
  });

  it("reloads the newer server snapshot after a revision conflict", async () => {
    const newerState = {
      ...remoteState,
      revision: 3,
      sessions: [{ ...remoteState.sessions[0], title: "其他页面更新的会话", updated_at: 3 }],
    };
    mocks.getChatState
      .mockResolvedValueOnce({ state: remoteState, updated_at: 2 })
      .mockResolvedValueOnce({ state: newerState, updated_at: 3 });
    mocks.saveChatState.mockRejectedValueOnce(new ApiError(
      409,
      "/chat/sessions",
      "聊天会话已更新",
      { code: "chat.state_conflict" },
    ));
    const { result, unmount } = renderHook(() => useChatSessionSync());
    await waitFor(() => expect(result.current).toBe("synced"));

    act(() => useChatStore.getState().renameSession("remote-session", "本地更新"));

    await waitFor(() => expect(mocks.getChatState).toHaveBeenCalledTimes(2), { timeout: 2_000 });
    await waitFor(() => {
      expect(useChatStore.getState().sessions[0]?.title).toBe("其他页面更新的会话");
      expect(result.current).toBe("synced");
    });
    unmount();
  });
});
