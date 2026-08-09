import { describe, expect, it } from "vitest";
import {
  errorMessage,
  formatInteger,
  formatMoney,
  formatPrice,
  formatTime,
} from "./portfolioFormatters";

describe("portfolio formatters", () => {
  it("formats monetary values and empty values", () => {
    expect(formatMoney(1234.5)).toBe("¥1,234.50");
    expect(formatMoney(null)).toBe("-");
    expect(formatPrice(12.34567)).toBe("¥12.3457");
    expect(formatInteger(1234)).toBe("1,234");
  });

  it("formats valid times and preserves invalid values", () => {
    expect(formatTime("2026-08-06T09:30:00")).toBe("2026-08-06 09:30");
    expect(formatTime("not-a-time")).toBe("not-a-time");
  });

  it("uses actionable error messages", () => {
    expect(errorMessage(new Error("request failed"))).toBe("request failed");
    expect(errorMessage("request failed")).toBe("操作失败，请稍后重试");
  });
});
