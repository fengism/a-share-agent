import { beforeEach, describe, expect, it, vi } from "vitest";
import { queryClient } from "../api/queryClient";
import { queryKeys } from "../api/queryKeys";
import {
  getActiveUserScope,
  registerUserScopeHandler,
  setActiveUserScope,
} from "./userScope";

describe("userScope", () => {
  beforeEach(() => {
    setActiveUserScope(null);
    queryClient.clear();
  });

  it("clears query data and notifies handlers when the user changes", () => {
    queryClient.setQueryData(queryKeys.portfolio, { owner: "alice" });
    const handler = vi.fn();
    const unregister = registerUserScopeHandler(handler);

    setActiveUserScope(1);

    expect(queryClient.getQueryData(["portfolio"])).toBeUndefined();
    expect(getActiveUserScope()).toBe(1);
    expect(handler).toHaveBeenCalledWith(1, null);
    unregister();
  });

  it("does not clear or notify when the user id is unchanged", () => {
    setActiveUserScope(1);
    queryClient.setQueryData(queryKeys.portfolio, { owner: "alice" });
    const handler = vi.fn();
    const unregister = registerUserScopeHandler(handler);

    setActiveUserScope(1);

    expect(queryClient.getQueryData(["portfolio"])).toEqual({ owner: "alice" });
    expect(handler).not.toHaveBeenCalled();
    unregister();
  });
});
