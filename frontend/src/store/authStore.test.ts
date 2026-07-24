import { describe, it, expect, beforeEach, vi } from "vitest";

vi.mock("../api/auth", () => ({
  loginApi: vi.fn(),
  registerApi: vi.fn(),
  logoutApi: vi.fn(),
  meApi: vi.fn(),
}));

import { loginApi, registerApi, logoutApi, meApi } from "../api/auth";
import { useAuthStore } from "./authStore";
import { getToken, setToken } from "../api/authToken";

const asMock = (fn: unknown) => fn as unknown as ReturnType<typeof vi.fn>;

describe("authStore", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setToken(null);
    useAuthStore.setState({ user: null, bootstrapped: false });
  });

  it("login persists the token and user", async () => {
    asMock(loginApi).mockResolvedValue({ token: "tok", user: { id: 1, username: "alice", is_admin: false } });
    await useAuthStore.getState().login("alice", "pw123456");
    expect(loginApi).toHaveBeenCalledWith({ username: "alice", password: "pw123456" });
    expect(getToken()).toBe("tok");
    expect(useAuthStore.getState().user?.username).toBe("alice");
  });

  it("register forwards the invite code and stores the session", async () => {
    asMock(registerApi).mockResolvedValue({ token: "t2", user: { id: 2, username: "bob", is_admin: false } });
    await useAuthStore.getState().register("bob", "pw123456", "INVITE1");
    expect(registerApi).toHaveBeenCalledWith({ username: "bob", password: "pw123456", invite_code: "INVITE1" });
    expect(getToken()).toBe("t2");
    expect(useAuthStore.getState().user?.username).toBe("bob");
  });

  it("logout clears token and user", async () => {
    setToken("x");
    useAuthStore.setState({ user: { id: 1, username: "alice", is_admin: false } });
    asMock(logoutApi).mockResolvedValue({ ok: true });
    await useAuthStore.getState().logout();
    expect(getToken()).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
  });

  it("clearLocal drops the session without calling the API", () => {
    setToken("x");
    useAuthStore.setState({ user: { id: 1, username: "alice", is_admin: false } });
    useAuthStore.getState().clearLocal();
    expect(getToken()).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
    expect(logoutApi).not.toHaveBeenCalled();
  });

  it("bootstrap without a token marks bootstrapped and skips /me", async () => {
    await useAuthStore.getState().bootstrap();
    expect(meApi).not.toHaveBeenCalled();
    expect(useAuthStore.getState().bootstrapped).toBe(true);
    expect(useAuthStore.getState().user).toBeNull();
  });

  it("bootstrap with a valid token loads the user", async () => {
    setToken("tok");
    asMock(meApi).mockResolvedValue({ id: 1, username: "alice", is_admin: true });
    await useAuthStore.getState().bootstrap();
    expect(useAuthStore.getState().user?.is_admin).toBe(true);
    expect(useAuthStore.getState().bootstrapped).toBe(true);
  });

  it("bootstrap with an invalid token clears the session", async () => {
    setToken("bad");
    asMock(meApi).mockRejectedValue(new Error("401"));
    await useAuthStore.getState().bootstrap();
    expect(getToken()).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().bootstrapped).toBe(true);
  });
});
