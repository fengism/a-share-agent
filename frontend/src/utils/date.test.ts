import { describe, it, expect } from "vitest";
import dayjs from "dayjs";
import { oneYearAgoDate } from "./date";

describe("date utils", () => {
  it("oneYearAgoDate returns an 8-digit YYYYMMDD one year ago", () => {
    const v = oneYearAgoDate();
    expect(v).toMatch(/^\d{8}$/);
    expect(v).toBe(dayjs().subtract(1, "year").format("YYYYMMDD"));
  });
});
