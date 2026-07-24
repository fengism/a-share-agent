import { describe, it, expect } from "vitest";
import {
  formatSignedPercent, formatRatioPercent, formatHotValue, formatWanAmount,
  formatNumber, formatMarketCap, formatAmount, formatAmountWanYi, changeColor,
} from "./format";
import { themes } from "../theme/themes";

const c = themes["stellar-blue"].colors;

describe("format utils", () => {
  it("formatSignedPercent", () => {
    expect(formatSignedPercent(1.234)).toBe("+1.23%");
    expect(formatSignedPercent(-0.5)).toBe("-0.50%");
    expect(formatSignedPercent(0)).toBe("0.00%");
    expect(formatSignedPercent(null)).toBe("-");
    expect(formatSignedPercent(undefined)).toBe("-");
  });

  it("formatRatioPercent", () => {
    expect(formatRatioPercent(0.1234)).toBe("12.3%");
    expect(formatRatioPercent(1)).toBe("100.0%");
    expect(formatRatioPercent(null)).toBe("-");
  });

  it("formatHotValue", () => {
    expect(formatHotValue(12345)).toBe("1.2万");
    expect(formatHotValue(999)).toBe("999");
    expect(formatHotValue(null)).toBe("-");
  });

  it("formatWanAmount", () => {
    expect(formatWanAmount(5000)).toBe("5000万");
    expect(formatWanAmount(12345)).toBe("1.23亿");
    expect(formatWanAmount(null)).toBe("-");
  });

  it("formatNumber", () => {
    expect(formatNumber(3.14159)).toBe("3.14");
    expect(formatNumber(3.14159, 3)).toBe("3.142");
    expect(formatNumber(null)).toBe("-");
  });

  it("formatMarketCap", () => {
    expect(formatMarketCap(2.5e12)).toBe("2.50万亿");
    expect(formatMarketCap(3e8)).toBe("3.00亿");
    expect(formatMarketCap(500)).toBe("500");
    expect(formatMarketCap(null)).toBe("-");
  });

  it("formatAmount", () => {
    expect(formatAmount(2.5e8)).toBe("2.5亿");
    expect(formatAmount(3e4)).toBe("3.0万");
    expect(formatAmount(500)).toBe("500");
    expect(formatAmount(null)).toBe("-");
  });

  it("formatAmountWanYi", () => {
    expect(formatAmountWanYi(2.5e8)).toBe("2.50亿");
    expect(formatAmountWanYi(3e4)).toBe("3.00万");
    expect(formatAmountWanYi(null)).toBe("-");
  });

  it("changeColor maps sign to theme colors", () => {
    expect(changeColor(1, c)).toBe(c.up);
    expect(changeColor(-1, c)).toBe(c.down);
    expect(changeColor(0, c)).toBe(c.textSecondary);
    expect(changeColor(null, c)).toBe(c.textSecondary);
  });
});
