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
import { getActiveUserScope, setActiveUserScope } from "./userScope";

const asMock = (fn: unknown) => fn as unknown as ReturnType<typeof vi.fn>;

describe("authStore", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setActiveUserScope(null);
    setToken(null);
    useAuthStore.setState({ user: null, bootstrapped: false });
  });

  it("login relies on the HttpOnly cookie and stores the user", async () => {
    asMock(loginApi).mockResolvedValue({ token: "tok", user: { id: 1, username: "alice", is_admin: false, must_change_password: false } });
    await useAuthStore.getState().login("alice", "pw123456");
    expect(loginApi).toHaveBeenCalledWith({ username: "alice", password: "pw123456" });
    expect(getToken()).toBeNull();
    expect(useAuthStore.getState().user?.username).toBe("alice");
    expect(getActiveUserScope()).toBe(1);
  });

  it("register forwards the invite code and relies on the HttpOnly cookie", async () => {
    asMock(registerApi).mockResolvedValue({ token: "t2", user: { id: 2, username: "bob", is_admin: false, must_change_password: false } });
    await useAuthStore.getState().register("bob", "pw123456", "INVITE1");
    expect(registerApi).toHaveBeenCalledWith({ username: "bob", password: "pw123456", invite_code: "INVITE1" });
    expect(getToken()).toBeNull();
    expect(useAuthStore.getState().user?.username).toBe("bob");
    expect(getActiveUserScope()).toBe(2);
  });

  it("logout clears token and user", async () => {
    setToken("x");
    setActiveUserScope(1);
    useAuthStore.setState({ user: { id: 1, username: "alice", is_admin: false, must_change_password: false } });
    asMock(logoutApi).mockResolvedValue({ ok: true });
    await useAuthStore.getState().logout();
    expect(getToken()).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
    expect(getActiveUserScope()).toBeNull();
  });

  it("clearLocal drops the session without calling the API", () => {
    setToken("x");
    setActiveUserScope(1);
    useAuthStore.setState({ user: { id: 1, username: "alice", is_admin: false, must_change_password: false } });
    useAuthStore.getState().clearLocal();
    expect(getToken()).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
    expect(getActiveUserScope()).toBeNull();
    expect(logoutApi).not.toHaveBeenCalled();
  });

  it("bootstrap checks the cookie session through /me", async () => {
    asMock(meApi).mockResolvedValue({ id: 1, username: "alice", is_admin: true, must_change_password: false });
    await useAuthStore.getState().bootstrap();
    expect(meApi).toHaveBeenCalledTimes(1);
    expect(useAuthStore.getState().bootstrapped).toBe(true);
    expect(useAuthStore.getState().user?.is_admin).toBe(true);
    expect(getActiveUserScope()).toBe(1);
  });

  it("bootstrap with an invalid cookie session clears local user state", async () => {
    asMock(meApi).mockRejectedValue(new Error("401"));
    await useAuthStore.getState().bootstrap();
    expect(getToken()).toBeNull();
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().bootstrapped).toBe(true);
    expect(getActiveUserScope()).toBeNull();
  });

  it("refreshUser updates the active user scope", async () => {
    asMock(meApi).mockResolvedValue({ id: 3, username: "carol", is_admin: false, must_change_password: false });

    await useAuthStore.getState().refreshUser();

    expect(useAuthStore.getState().user?.username).toBe("carol");
    expect(getActiveUserScope()).toBe(3);
  });
});
