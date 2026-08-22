import { describe, it, expect } from "vitest";
import dayjs from "dayjs";
import { normalizeIsoDate, oneYearAgoDate } from "./date";

describe("date utils", () => {
  it("oneYearAgoDate returns an 8-digit YYYYMMDD one year ago", () => {
    const v = oneYearAgoDate();
    expect(v).toMatch(/^\d{8}$/);
    expect(v).toBe(dayjs().subtract(1, "year").format("YYYYMMDD"));
  });

  it("normalizes malformed ISO dates to the fallback", () => {
    expect(normalizeIsoDate("2026-08-13", "2026-08-14")).toBe("2026-08-13");
    expect(normalizeIsoDate("2026-02-30", "2026-08-14")).toBe("2026-08-14");
    expect(normalizeIsoDate("not-a-date", "2026-08-14")).toBe("2026-08-14");
  });
});
