import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAStockTradingSession } from "./useAStockTradingSession";

describe("useAStockTradingSession", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("resumes automatic refresh when the Shanghai morning session opens", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-14T01:14:59.900Z"));
    const { result, unmount } = renderHook(() => useAStockTradingSession());

    expect(result.current).toBe(false);

    act(() => {
      vi.advanceTimersByTime(100);
    });

    expect(result.current).toBe(true);
    unmount();
  });

  it("shares one boundary timer across concurrent consumers", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-08-14T01:14:00.000Z"));
    const setTimeoutSpy = vi.spyOn(window, "setTimeout");

    const first = renderHook(() => useAStockTradingSession());
    const second = renderHook(() => useAStockTradingSession());

    expect(setTimeoutSpy).toHaveBeenCalledTimes(1);
    first.unmount();
    second.unmount();
  });
});
