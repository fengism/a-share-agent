import { describe, it, expect } from "vitest";
import {
  getSourceColor, getSourceLabel, getSourcePlatform, isTwitterItem,
  formatTime, getTimeColor, getSentimentConfig, clampPage,
  getRelativeTimeRefreshDelay,
} from "./feedHelpers";
import { themes } from "../../theme/themes";
import type { FeedNewsItem } from "../../types/stock";

const c = themes["stellar-blue"].colors;
const item = (source: string): FeedNewsItem => ({ source } as unknown as FeedNewsItem);

describe("shared feed helpers", () => {
  it("getSourcePlatform groups by platform", () => {
    expect(getSourcePlatform("财联社快讯")).toBe("7×24 快讯");
    expect(getSourcePlatform("东方财富")).toBe("东方财富");
    expect(getSourcePlatform("某未知源")).toBe("其他");
  });

  it("isTwitterItem", () => {
    expect(isTwitterItem(item("Twitter"))).toBe(true);
    expect(isTwitterItem(item("东方财富"))).toBe(false);
  });

  it("getSourceColor prefers kuaixun accent then source map", () => {
    expect(getSourceColor("财联社快讯", c)).toBe(c.warning);
    expect(getSourceColor("东方财富", c)).toBe(c.primary);
    expect(getSourceColor("财联社", c)).toBe(c.up);
    expect(getSourceColor("未知源", c)).toBe(c.textMuted);
  });

  it("getSourceLabel", () => {
    expect(getSourceLabel("盘中快讯", c)).toBe("7×24 快讯");
    expect(getSourceLabel("", c)).toBe("未知");
    expect(getSourceLabel("东方财富", c)).toBe("东方财富");
  });

  it("formatTime handles empty and invalid input", () => {
    expect(formatTime("")).toBe("");
    expect(formatTime("not-a-date")).toBe("not-a-date");
  });

  it("getTimeColor returns muted for invalid input", () => {
    expect(getTimeColor("not-a-date", c)).toBe(c.textMuted);
  });

  it("getSentimentConfig maps sentiment to theme colors", () => {
    const cfg = getSentimentConfig(c);
    expect(cfg["偏多"].color).toBe(c.up);
    expect(cfg["偏空"].color).toBe(c.down);
    expect(cfg["中性"].color).toBe(c.accent);
  });

  it("clampPage keeps the page within available data", () => {
    expect(clampPage(3, 45, 20)).toBe(3);
    expect(clampPage(4, 45, 20)).toBe(3);
    expect(clampPage(0, 45, 20)).toBe(1);
  });

  it("clampPage handles empty data and invalid page sizes", () => {
    expect(clampPage(5, 0, 20)).toBe(1);
    expect(clampPage(5, 10, 0)).toBe(1);
  });

  it("aligns relative time refreshes to the next minute boundary", () => {
    expect(getRelativeTimeRefreshDelay(120_000)).toBe(60_000);
    expect(getRelativeTimeRefreshDelay(120_001)).toBe(59_999);
    expect(getRelativeTimeRefreshDelay(179_999)).toBe(1);
  });

  it("falls back to one minute for invalid clocks", () => {
    expect(getRelativeTimeRefreshDelay(Number.NaN)).toBe(60_000);
    expect(getRelativeTimeRefreshDelay(-1)).toBe(60_000);
  });
});
