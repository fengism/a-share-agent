import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  getCsrfToken,
  getToken,
  notifyUnauthorized,
  setToken,
  setUnauthorizedHandler,
} from "./authToken";

describe("authToken", () => {
  beforeEach(() => {
    setToken(null);
    setUnauthorizedHandler(null);
    document.cookie = "a_share_csrf=; Max-Age=0; path=/";
  });

  it("stores legacy bearer tokens in memory only", () => {
    setToken("abc.def");
    expect(getToken()).toBe("abc.def");
    expect(localStorage.getItem("a-share-agent-token")).toBeNull();
  });

  it("clears the in-memory legacy token", () => {
    setToken("abc");
    setToken(null);
    expect(getToken()).toBeNull();
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

  it("reads the double-submit CSRF cookie", () => {
    document.cookie = "a_share_csrf=csrf-token; path=/";
    expect(getCsrfToken()).toBe("csrf-token");
  });
});
