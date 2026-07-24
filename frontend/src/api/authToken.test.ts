import { describe, it, expect, beforeEach, vi } from "vitest";
import { getToken, setToken, setUnauthorizedHandler, notifyUnauthorized } from "./authToken";

const TOKEN_KEY = "a-share-agent-token";

describe("authToken", () => {
  beforeEach(() => {
    localStorage.clear();
    setToken(null);
    setUnauthorizedHandler(null);
  });

  it("stores and reads the token in memory and localStorage", () => {
    setToken("abc.def");
    expect(getToken()).toBe("abc.def");
    expect(localStorage.getItem(TOKEN_KEY)).toBe("abc.def");
  });

  it("clears the token from memory and localStorage", () => {
    setToken("abc");
    setToken(null);
    expect(getToken()).toBeNull();
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("invokes the registered unauthorized handler", () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    notifyUnauthorized();
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("does not throw when notifying with no handler set", () => {
    setUnauthorizedHandler(null);
    expect(() => notifyUnauthorized()).not.toThrow();
  });

  it("rehydrates the token from localStorage on module load", async () => {
    localStorage.setItem(TOKEN_KEY, "persisted-token");
    vi.resetModules();
    const fresh = await import("./authToken");
    expect(fresh.getToken()).toBe("persisted-token");
  });
});
