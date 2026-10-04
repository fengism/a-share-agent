import { describe, expect, it } from "vitest";
import { buildIntradayVisibleRange } from "./intradayTimeRange";

describe("buildIntradayVisibleRange", () => {
  it("fixes the selected trading day to 09:30–15:00", () => {
    const point = Date.UTC(2026, 7, 21, 11, 30) / 1000;

    const range = buildIntradayVisibleRange(point);

    expect(range).toEqual({
      from: Date.UTC(2026, 7, 21, 9, 30) / 1000,
      to: Date.UTC(2026, 7, 21, 15, 0) / 1000,
    });
    expect(range!.to - range!.from).toBe(5.5 * 60 * 60);
  });

  it("fixes the selected trading day to 09:30–16:00 for HK market", () => {
    const point = Date.UTC(2026, 7, 21, 11, 30) / 1000;

    const range = buildIntradayVisibleRange(point, "hk");

    expect(range).toEqual({
      from: Date.UTC(2026, 7, 21, 9, 30) / 1000,
      to: Date.UTC(2026, 7, 21, 16, 0) / 1000,
    });
    expect(range!.to - range!.from).toBe(6.5 * 60 * 60);
  });

  it("rejects invalid timestamps", () => {
    expect(buildIntradayVisibleRange(Number.NaN)).toBeNull();
    expect(buildIntradayVisibleRange(Number.POSITIVE_INFINITY)).toBeNull();
  });
});
