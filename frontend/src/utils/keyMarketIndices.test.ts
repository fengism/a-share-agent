import { describe, expect, it } from "vitest";
import {
  HEADER_TICKER_INDEX_COUNT,
  isHeaderTickerIndex,
  KEY_MARKET_INDEX_CODES,
  KEY_MARKET_INDICES,
} from "./keyMarketIndices";

describe("keyMarketIndices", () => {
  it("代码唯一且与展示名一一对应", () => {
    const codes = KEY_MARKET_INDICES.map((item) => item.code);
    expect(new Set(codes).size).toBe(codes.length);
    for (const item of KEY_MARKET_INDICES) {
      expect(item.name).not.toBe("");
    }
  });

  it("KEY_MARKET_INDEX_CODES 与列表顺序一致", () => {
    expect(KEY_MARKET_INDEX_CODES).toEqual(KEY_MARKET_INDICES.map((item) => item.code));
    expect(KEY_MARKET_INDEX_CODES).toEqual([
      "000001",
      "399001",
      "399006",
      "000688",
      "000300",
      "000905",
    ]);
  });

  it("顶栏行情条恰好展示三个指数", () => {
    expect(HEADER_TICKER_INDEX_COUNT).toBe(3);
    const headerCodes = KEY_MARKET_INDICES.filter((item) => item.inHeaderTicker).map(
      (item) => item.code,
    );
    expect(headerCodes).toEqual(["000001", "399001", "399006"]);
  });

  it("按裸代码匹配顶栏指数", () => {
    expect(isHeaderTickerIndex({ code: "000001", name: "上证指数" })).toBe(true);
    expect(isHeaderTickerIndex({ code: "399006", name: "创业板指" })).toBe(true);
  });

  it("按带交易所前缀的代码兜底匹配", () => {
    expect(isHeaderTickerIndex({ code: "sh000001", name: "" })).toBe(true);
    expect(isHeaderTickerIndex({ code: "sz399001", name: "" })).toBe(true);
  });

  it("按中文简称兜底匹配（数据源代码不可用时）", () => {
    expect(isHeaderTickerIndex({ code: "", name: "上证指数" })).toBe(true);
    expect(isHeaderTickerIndex({ code: "unknown", name: "创业板指 399006" })).toBe(true);
  });

  it("非顶栏指数与空值都不匹配", () => {
    // 000688/000300/000905 只在指数页展示，不进顶栏
    expect(isHeaderTickerIndex({ code: "000688", name: "科创50" })).toBe(false);
    expect(isHeaderTickerIndex({ code: "000300", name: "沪深300" })).toBe(false);
    expect(isHeaderTickerIndex({ code: "000905", name: "中证500" })).toBe(false);
    expect(isHeaderTickerIndex({})).toBe(false);
    expect(isHeaderTickerIndex({ code: null, name: null })).toBe(false);
    expect(isHeaderTickerIndex({ code: "", name: "" })).toBe(false);
  });

  it("兜底匹配不会把无关指数误判为顶栏指数", () => {
    expect(isHeaderTickerIndex({ code: "600519", name: "贵州茅台" })).toBe(false);
  });
});
