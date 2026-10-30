import { describe, it, expect } from "vitest";
import {
  getSourceColor, getSourceLabel, getSourcePlatform, isTwitterItem,
  formatTime, getTimeColor, getSentimentConfig, clampPage,
  getRelativeTimeRefreshDelay, cleanNewsTitle, normalizeNewsTitle,
  computeHeadlineSimilarity, clusterNewsItems,
} from "./feedHelpers";
import { themes } from "../../theme/themes";
import type { FeedNewsItem } from "../../types/stock";

const c = themes["stellar-blue"].colors;
const item = (source: string): FeedNewsItem => ({ source } as unknown as FeedNewsItem);

describe("shared feed helpers", () => {
  it("getSourcePlatform groups by platform", () => {
    expect(getSourcePlatform("财联社快讯")).toBe("7×24 快讯");
    expect(getSourcePlatform("财联社7×24快讯")).toBe("7×24 快讯");
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
    expect(getSourceLabel("东方财富", c)).toBe(c.primary ? "东方财富" : "东方财富");
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

  describe("news deduplication and clustering", () => {
    it("cleanNewsTitle strips wire tags and media suffixes", () => {
      expect(cleanNewsTitle("【快讯】央行今日开展2000亿元逆回购操作（新浪财经）"))
        .toBe("央行今日开展2000亿元逆回购操作");
      expect(cleanNewsTitle("【财联社10月29日电】商务部召开例行新闻发布会 - 东方财富网"))
        .toBe("商务部召开例行新闻发布会");
      expect(cleanNewsTitle("高盛上调中国股票评级至超配 —— 华尔街见闻"))
        .toBe("高盛上调中国股票评级至超配");
    });

    it("normalizeNewsTitle normalizes whitespace and punctuation", () => {
      expect(normalizeNewsTitle("  央行： 降准 0.5%！ "))
        .toBe("央行降准05");
    });

    it("computeHeadlineSimilarity calculates LCS ratio accurately", () => {
      const s1 = "央行开展2000亿元逆回购操作中标利率1.5%";
      const s2 = "央行今日开展2000亿元逆回购操作中标利率1.5%";
      const sim = computeHeadlineSimilarity(s1, s2);
      expect(sim).toBeGreaterThan(0.9);

      const unrelated = "商务部谈中美经贸摩擦磋商最新进展";
      expect(computeHeadlineSimilarity(s1, unrelated)).toBeLessThan(0.3);
    });

    it("clusterNewsItems merges similar news from different sources", () => {
      const items: FeedNewsItem[] = [
        {
          id: "1",
          title: "【快讯】央行开展2000亿元逆回购操作",
          content: "7天期逆回购...",
          source: "财联社快讯",
          publish_time: "2026-10-29 09:30:00",
        } as unknown as FeedNewsItem,
        {
          id: "2",
          title: "央行今日开展2000亿元逆回购操作（新浪财经）",
          content: "中国央行开展2000亿...",
          source: "新浪财经",
          publish_time: "2026-10-29 09:32:00",
        } as unknown as FeedNewsItem,
        {
          id: "3",
          title: "商务部就美对华芯片出口管制发表声明",
          content: "商务部新闻发言人...",
          source: "新华网",
          publish_time: "2026-10-29 09:35:00",
        } as unknown as FeedNewsItem,
      ];

      const clustered = clusterNewsItems(items, true);
      expect(clustered.length).toBe(2);
      expect(clustered[0].title).toBe("【快讯】央行开展2000亿元逆回购操作");
      expect(clustered[0].otherSources).toEqual(["新浪财经"]);
      expect(clustered[1].title).toBe("商务部就美对华芯片出口管制发表声明");
    });

    it("clusterNewsItems returns items as-is when disabled", () => {
      const items: FeedNewsItem[] = [
        { id: "1", title: "相同标题", source: "A" } as unknown as FeedNewsItem,
        { id: "2", title: "相同标题", source: "B" } as unknown as FeedNewsItem,
      ];
      const clustered = clusterNewsItems(items, false);
      expect(clustered.length).toBe(2);
    });
  });
});
