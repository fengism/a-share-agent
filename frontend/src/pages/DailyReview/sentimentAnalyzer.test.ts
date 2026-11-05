import { describe, expect, it } from "vitest";
import { analyzeSentiment } from "./sentimentAnalyzer";
import type { DailyReviewPayload, ReviewHeadline } from "./reviewView";

describe("analyzeSentiment", () => {
  it("derives sentiment score, zone, and tactics accurately", () => {
    const review: DailyReviewPayload = {
      date: "2026-10-29",
      title: "每日复盘",
      market_summary: "测试大盘复盘",
      data_snapshot: {
        indices: [{ name: "上证指数", change_pct: 1.2 }],
        hot_stocks: [],
        hot_concepts: [],
        hot_industries: [],
        dragon_tiger: [],
        market_news: [],
        market_statistics: { limit_up_count: 45, break_rate: 0.15 },
        market_emotion: { up_count: 3800, down_count: 1200 },
        top_sectors: [],
        bottom_sectors: [],
        market_volume: { total_turnover: 18000 },
        macro_data: {},
      },
      sentiment_cycle: { stage: "主升共振", evidence: ["连板高度打开"] },
    };

    const headline: ReviewHeadline = {
      limitUpCount: 45,
      breakRate: 15.0,
      indexChangePct: 1.2,
      indexName: "上证指数",
      stage: "主升共振",
      quality: "complete",
      generation: "ai",
      checkHit: 3,
      checkTotal: 4,
    };

    const result = analyzeSentiment(review, headline);

    expect(result.temperature).toBeGreaterThan(65);
    expect(result.zoneCode).toBe("HOT");
    expect(result.zoneLabel).toBe("偏热活跃区");
    expect(result.tactics).toContain("顺势持筹");
    expect(result.factors.breadth).toBe(76);
    expect(result.factors.momentum).toBe(74);
    expect(result.factors.stability).toBe(78);
  });

  it("identifies cold ice zone during market pullbacks", () => {
    const review: DailyReviewPayload = {
      date: "2026-10-28",
      title: "每日复盘",
      market_summary: "冰点下挫",
      data_snapshot: {
        indices: [{ name: "上证指数", change_pct: -2.5 }],
        hot_stocks: [],
        hot_concepts: [],
        hot_industries: [],
        dragon_tiger: [],
        market_news: [],
        market_statistics: { limit_up_count: 5, break_rate: 0.65 },
        market_emotion: { up_count: 500, down_count: 4500 },
        top_sectors: [],
        bottom_sectors: [],
        market_volume: { total_turnover: 6500 },
        macro_data: {},
      },
      sentiment_cycle: { stage: "冰点", evidence: ["高位核按钮跌停潮"] },
    };

    const headline: ReviewHeadline = {
      limitUpCount: 5,
      breakRate: 65.0,
      indexChangePct: -2.5,
      indexName: "上证指数",
      stage: "冰点",
      quality: "complete",
      generation: "ai",
      checkHit: null,
      checkTotal: null,
    };

    const result = analyzeSentiment(review, headline);

    expect(result.temperature).toBeLessThanOrEqual(25);
    expect(result.tactics).toContain("切忌恐慌杀跌");
  });
});
