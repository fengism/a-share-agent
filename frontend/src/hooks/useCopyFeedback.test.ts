import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useCopyFeedback } from "./useCopyFeedback";

describe("useCopyFeedback", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("starts in the not-copied state", () => {
    const { result } = renderHook(() => useCopyFeedback());
    expect(result.current.copied).toBe(false);
  });

  it("resets copied after the configured duration", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useCopyFeedback(2000));

    act(() => result.current.markCopied());
    expect(result.current.copied).toBe(true);

    act(() => vi.advanceTimersByTime(1999));
    expect(result.current.copied).toBe(true);

    act(() => vi.advanceTimersByTime(1));
    expect(result.current.copied).toBe(false);
  });

  it("restarts the timer instead of stacking on repeated copies", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useCopyFeedback(2000));

    act(() => result.current.markCopied());
    act(() => vi.advanceTimersByTime(1500));
    act(() => result.current.markCopied());

    // 若旧计时器未被取消，这里会提前复位。
    act(() => vi.advanceTimersByTime(1000));
    expect(result.current.copied).toBe(true);

    act(() => vi.advanceTimersByTime(1000));
    expect(result.current.copied).toBe(false);
  });

  it("clears the pending timer on unmount so no state update fires afterwards", () => {
    vi.useFakeTimers();
    const clearSpy = vi.spyOn(window, "clearTimeout");
    const { result, unmount } = renderHook(() => useCopyFeedback(2000));

    act(() => result.current.markCopied());
    unmount();

    expect(clearSpy).toHaveBeenCalled();
    // 计时器已取消，推进时间不应再触发任何回调（否则就是对已卸载组件 setState）。
    expect(vi.getTimerCount()).toBe(0);
  });

  it("resetCopied clears immediately without waiting for the timer", () => {
    vi.useFakeTimers();
    const { result } = renderHook(() => useCopyFeedback(2000));

    act(() => result.current.markCopied());
    act(() => result.current.resetCopied());

    expect(result.current.copied).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
  });
});
