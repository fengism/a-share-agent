import { describe, expect, it } from "vitest";
import { getNextVisibleCount, getVisibleMessageStart } from "./chatListHelpers";

describe("chat list helpers", () => {
  it("selects the tail of a long conversation", () => {
    expect(getVisibleMessageStart(100, 60)).toBe(40);
  });

  it("shows the full conversation when it is shorter than the limit", () => {
    expect(getVisibleMessageStart(20, 60)).toBe(0);
  });

  it("loads earlier messages without exceeding the total", () => {
    expect(getNextVisibleCount(60, 120, 40)).toBe(100);
    expect(getNextVisibleCount(100, 120, 40)).toBe(120);
  });
});
