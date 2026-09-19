import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useHKStockTradingSession } from "./useHKStockTradingSession";

describe("useHKStockTradingSession", () => {
  it("returns a boolean session status", () => {
    const { result } = renderHook(() => useHKStockTradingSession());
    expect(typeof result.current).toBe("boolean");
  });
});
