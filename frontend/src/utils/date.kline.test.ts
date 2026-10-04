import { describe, expect, it } from "vitest";
import dayjs from "dayjs";
import {
  MAX_KLINE_HISTORY_YEARS,
  isAtKlineHistoryLimit,
  oneYearAgoDate,
  yearsAgoDate,
} from "./date";

describe("K 线历史窗口", () => {
  it("默认展示近 1 年", () => {
    expect(oneYearAgoDate()).toBe(dayjs().subtract(1, "year").format("YYYYMMDD"));
    expect(yearsAgoDate(1)).toBe(dayjs().subtract(1, "year").format("YYYYMMDD"));
  });

  it("支持按年向前扩充", () => {
    expect(yearsAgoDate(3)).toBe(dayjs().subtract(3, "year").format("YYYYMMDD"));
    expect(yearsAgoDate(10)).toBe(dayjs().subtract(10, "year").format("YYYYMMDD"));
  });

  it("最多回溯 10 年", () => {
    expect(MAX_KLINE_HISTORY_YEARS).toBe(10);
    expect(yearsAgoDate(25)).toBe(yearsAgoDate(MAX_KLINE_HISTORY_YEARS));
    expect(yearsAgoDate(-3)).toBe(dayjs().format("YYYYMMDD"));
  });

  it("判断是否触达上限", () => {
    expect(isAtKlineHistoryLimit(yearsAgoDate(MAX_KLINE_HISTORY_YEARS))).toBe(true);
    expect(isAtKlineHistoryLimit(yearsAgoDate(9))).toBe(false);
    expect(isAtKlineHistoryLimit(yearsAgoDate(1))).toBe(false);
    expect(isAtKlineHistoryLimit("")).toBe(false);
  });
});