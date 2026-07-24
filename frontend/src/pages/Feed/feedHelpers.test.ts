import { describe, it, expect } from "vitest";
import {
  getSourceColor, getSourceLabel, getSourcePlatform, isTwitterItem,
  formatTime, getTimeColor, getSentimentConfig, KUAIXUN_ACCENT,
} from "./feedHelpers";
import { themes } from "../../theme/themes";
import type { FeedNewsItem } from "../../types/stock";

const c = themes["stellar-blue"].colors;
const item = (source: string): FeedNewsItem => ({ source } as unknown as FeedNewsItem);

describe("feedHelpers", () => {
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
    expect(getSourceColor("财联社快讯", c)).toBe(KUAIXUN_ACCENT);
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
});
