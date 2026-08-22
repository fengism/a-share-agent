import { describe, expect, it } from "vitest";
import {
  isAStockAutoRefreshTime,
  millisecondsUntilNextAStockSessionBoundary,
} from "./tradingSession";

describe("A-share automatic refresh session", () => {
  it.each([
    ["2026-08-14T01:14:59.000Z", false],
    ["2026-08-14T01:15:00.000Z", true],
    ["2026-08-14T03:30:59.000Z", true],
    ["2026-08-14T03:31:00.000Z", false],
    ["2026-08-14T05:00:00.000Z", true],
    ["2026-08-14T07:10:59.000Z", true],
    ["2026-08-14T07:11:00.000Z", false],
    ["2026-08-15T02:00:00.000Z", false],
  ])("evaluates %s in Asia/Shanghai", (value, expected) => {
    expect(isAStockAutoRefreshTime(new Date(value))).toBe(expected);
  });

  it("schedules the next lunch boundary instead of polling the clock", () => {
    const now = new Date("2026-08-14T03:30:30.000Z");

    expect(millisecondsUntilNextAStockSessionBoundary(now)).toBe(30_000);
  });

  it("skips the weekend when calculating the next opening boundary", () => {
    const fridayAfterClose = new Date("2026-08-14T08:00:00.000Z");
    const mondayOpen = new Date("2026-08-17T01:15:00.000Z");

    expect(millisecondsUntilNextAStockSessionBoundary(fridayAfterClose)).toBe(
      mondayOpen.getTime() - fridayAfterClose.getTime(),
    );
  });
});
