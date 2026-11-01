import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { usePriceFlash } from "./usePriceFlash";

describe("usePriceFlash", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns empty string on initial render", () => {
    const { result } = renderHook(() => usePriceFlash(10.5));
    expect(result.current).toBe("");
  });

  it("triggers tick-flash-up when price rises and clears after duration", () => {
    const { result, rerender } = renderHook(({ price }) => usePriceFlash(price, 500), {
      initialProps: { price: 10.0 },
    });

    expect(result.current).toBe("");

    act(() => {
      rerender({ price: 10.5 });
    });

    expect(result.current).toBe("tick-flash-up");

    act(() => {
      vi.advanceTimersByTime(500);
    });

    expect(result.current).toBe("");
  });

  it("triggers tick-flash-down when price falls and clears after duration", () => {
    const { result, rerender } = renderHook(({ price }) => usePriceFlash(price, 400), {
      initialProps: { price: 12.0 },
    });

    act(() => {
      rerender({ price: 11.5 });
    });

    expect(result.current).toBe("tick-flash-down");

    act(() => {
      vi.advanceTimersByTime(400);
    });

    expect(result.current).toBe("");
  });

  it("does not trigger flash when price does not change or is nullish", () => {
    const { result, rerender } = renderHook(({ price }) => usePriceFlash(price), {
      initialProps: { price: null as number | null },
    });

    expect(result.current).toBe("");

    act(() => {
      rerender({ price: null });
    });
    expect(result.current).toBe("");

    act(() => {
      rerender({ price: 20 });
    });
    // First valid price after null does not trigger flash
    expect(result.current).toBe("");

    act(() => {
      rerender({ price: 20 });
    });
    expect(result.current).toBe("");
  });
});
