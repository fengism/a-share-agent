import { describe, expect, it } from "vitest";

import {
  formatMarketClock,
  formatMarketDate,
  formatMarketDateTime,
  formatMarketMonthDayClock,
  formatMarketPattern,
  formatMarketTime,
  marketDateStamp,
  parseMarketTime,
} from "./marketTime";

describe("parseMarketTime", () => {
  it("把无时区后缀的时间串按北京时间解释", () => {
    // 20:57 北京时间 = 12:57 UTC，不受运行环境时区影响
    expect(parseMarketTime("2026-10-22T20:57:00")?.toISOString()).toBe("2026-10-22T12:57:00.000Z");
    expect(parseMarketTime("2026-10-22 20:57:00")?.toISOString()).toBe("2026-10-22T12:57:00.000Z");
    expect(parseMarketTime("2026-10-22T20:57")?.toISOString()).toBe("2026-10-22T12:57:00.000Z");
    expect(parseMarketTime("2026-10-22T20:57:00.500")?.toISOString()).toBe(
      "2026-10-22T12:57:00.500Z",
    );
  });

  it("纯日期按北京时间零点解释，不会因浏览器时区回退一天", () => {
    expect(parseMarketTime("2026-10-22")?.toISOString()).toBe("2026-10-21T16:00:00.000Z");
  });

  it("已带时区后缀的串按绝对时刻保留", () => {
    expect(parseMarketTime("2026-10-22T20:57:00Z")?.toISOString()).toBe("2026-10-22T20:57:00.000Z");
    expect(parseMarketTime("2026-10-22T20:57:00+00:00")?.toISOString()).toBe(
      "2026-10-22T20:57:00.000Z",
    );
    expect(parseMarketTime("2026-10-22T20:57:00-05:00")?.toISOString()).toBe(
      "2026-10-23T01:57:00.000Z",
    );
  });

  it("数字同时兼容秒级与毫秒级 epoch", () => {
    expect(parseMarketTime(1792673820)?.toISOString()).toBe("2026-10-22T12:57:00.000Z");
    expect(parseMarketTime(1792673820000)?.toISOString()).toBe("2026-10-22T12:57:00.000Z");
  });

  it("非法输入返回 null", () => {
    expect(parseMarketTime("")).toBeNull();
    expect(parseMarketTime("   ")).toBeNull();
    expect(parseMarketTime("not-a-date")).toBeNull();
    expect(parseMarketTime(Number.NaN)).toBeNull();
    expect(parseMarketTime(new Date("bad"))).toBeNull();
    expect(parseMarketTime(null)).toBeNull();
    expect(parseMarketTime(undefined)).toBeNull();
  });

  it("Date 实例原样返回", () => {
    const date = new Date("2026-10-22T12:57:00Z");
    expect(parseMarketTime(date)).toBe(date);
  });
});

describe("formatMarket*", () => {
  it("按北京时间渲染，与浏览器时区无关", () => {
    expect(formatMarketDateTime("2026-10-22T20:57:00")).toBe("2026/10/22 20:57:00");
    expect(formatMarketDateTime("2026-10-22 20:57:00")).toBe("2026/10/22 20:57:00");
    expect(formatMarketDateTime("2026-10-22")).toBe("2026/10/22 00:00:00");
    expect(formatMarketDateTime(1792673820)).toBe("2026/10/22 20:57:00");
  });

  it("时钟/日期/月日时分各有独立格式", () => {
    expect(formatMarketClock("2026-10-22T09:30:00")).toBe("09:30");
    expect(formatMarketDate("2026-10-22")).toBe("2026/10/22");
    expect(formatMarketMonthDayClock("2026-10-22T20:57:00")).toBe("10/22 20:57");
  });

  it("解析失败时返回兜底文案", () => {
    expect(formatMarketDateTime("bad", "尚未更新")).toBe("尚未更新");
    expect(formatMarketDateTime(undefined)).toBe("-");
    expect(formatMarketClock(null, "尚未更新")).toBe("尚未更新");
    expect(formatMarketDate("")).toBe("-");
  });

  it("接受自定义 Intl 选项", () => {
    expect(
      formatMarketTime("2026-10-22T20:57:00", { year: "numeric", month: "long" }),
    ).toBe("2026年10月");
  });
});

describe("formatMarketPattern / marketDateStamp", () => {
  it("按模板渲染北京时间", () => {
    expect(formatMarketPattern("2026-10-22T20:57:03", "YYYY-MM-DD HH:mm")).toBe("2026-10-22 20:57");
    expect(formatMarketPattern("2026-10-22T20:57:03", "MM-DD HH:mm:ss")).toBe("10-22 20:57:03");
    expect(formatMarketPattern(1792673820, "YYYY-MM-DD HH:mm:ss")).toBe("2026-10-22 20:57:00");
  });

  it("模板里的未知片段原样保留", () => {
    expect(formatMarketPattern("2026-10-22T20:57:00", "YYYY年MM月DD日")).toBe("2026年10月22日");
    expect(formatMarketPattern("bad", "YYYY-MM-DD", "—")).toBe("—");
  });

  it("marketDateStamp 取北京时间的今天，跨 UTC 零点也不漂移", () => {
    // 2026-10-22T17:30Z = 北京 2026-10-23 01:30，UTC 日期仍是 22 日
    expect(marketDateStamp("2026-10-22T17:30:00Z")).toBe("2026-10-23");
    // 2026-10-22T15:59Z = 北京 2026-10-22 23:59
    expect(marketDateStamp("2026-10-22T15:59:00Z")).toBe("2026-10-22");
    expect(marketDateStamp()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});
