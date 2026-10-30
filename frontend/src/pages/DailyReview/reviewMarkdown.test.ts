import { describe, expect, it } from "vitest";
import {
  buildDailyReviewMarkdown,
  formatReviewTitle,
  renderReviewContent,
  stringifyReviewValue,
  unwrapJsonBlock,
} from "./reviewMarkdown";
import type { DailyReviewResult } from "../../types/dailyReview";

function makeReview(overrides: Record<string, unknown> = {}): DailyReviewResult {
  return {
    date: "2026-10-29",
    title: "A股市场每日复盘 - 2026-10-29",
    generated_at: "2026-10-29 16:10:00",
    market_summary: "指数震荡收涨。",
    quality_status: "complete",
    llm_review: "",
    index_review: { title: "指数复盘", summary: "缩量上行", bullets: ["银行护盘"] },
    hotspot_review: { title: "热点复盘", summary: "机器人领涨", bullets: [] },
    dragon_tiger_review: { title: "龙虎榜", summary: "机构净买入", bullets: [] },
    risk_alerts: ["高位股补跌"],
    opportunities: ["机器人"],
    strategy_notes: ["持股待涨"],
    data_snapshot: {
      indices: [{ name: "上证指数", change_pct: 0.85 }],
      hot_stocks: [],
      hot_concepts: [],
      hot_industries: [],
      dragon_tiger: [],
      top_sectors: [{ name: "机器人" }],
      bottom_sectors: [{ name: "白酒" }],
      market_news: [],
      market_volume: {},
      macro_data: {},
      source_status: { limit_up: { status: "partial", data_date: "2026-10-29", error: "接口超时" } },
    },
    ...overrides,
  } as unknown as DailyReviewResult;
}

describe("reviewMarkdown", () => {
  it("unwraps fenced json blocks", () => {
    expect(unwrapJsonBlock("```json\n{\"a\":1}\n```")).toBe('{"a":1}');
    expect(unwrapJsonBlock("plain")).toBe("plain");
  });

  it("stringifies nested values as markdown lists", () => {
    expect(stringifyReviewValue(["甲", "乙"])).toBe("- 甲\n- 乙");
    expect(stringifyReviewValue({ 结论: "偏多" })).toBe("- **结论**：偏多");
    expect(stringifyReviewValue({ 多行: "第一行\n第二行" })).toContain("  - 第一行");
  });

  it("renders json review content into titled sections", () => {
    const rendered = renderReviewContent('{"market_view":"偏多","risks":["补跌"]}');
    expect(rendered).toContain("## Market view");
    expect(rendered).toContain("## Risks");
  });

  it("keeps plain text review content untouched", () => {
    expect(renderReviewContent("直接的一段话")).toBe("直接的一段话");
  });

  it("formats field keys as readable titles", () => {
    expect(formatReviewTitle("market_view")).toBe("Market view");
  });

  it("builds the full markdown with every available section", () => {
    const markdown = buildDailyReviewMarkdown(
      makeReview({
        sentiment_cycle: { stage: "主升共振", ladder_health: "无断层", evidence: ["空间板 6 板"] },
        scenario_plans: [{ name: "超预期", trigger: "放量高开", playbook: "加仓主线", watch_levels: ["成交额 1.5 万亿"] }],
        next_day_watchlist: [{ name: "甲", role: "连板最高板", reason: "空间板", trigger: "竞价强度" }],
        key_levels: ["上证 3250 支撑"],
        previous_review_check: {
          review_date: "2026-10-28",
          verified_date: "2026-10-29",
          hit_count: 1,
          checked_count: 2,
          previous_limit_up_count: 55,
          limit_up_count: 42,
          watchlist: [
            { name: "甲", change_pct: 10, hit: true, limit_up: true },
            { name: "乙", missing: true },
          ],
          indices: [{ name: "上证指数", previous_change_pct: 0.8, change_pct: -0.42 }],
          note: "乙行情缺失",
        },
        cycle_trend: {
          points: [{ date: "2026-10-29", stage: "主升共振", limit_up_count: 42, break_rate: 0.15, index_change_pct: 1.2, stage_transition: "升级" }],
          stage_stats: [{ stage: "主升共振", occurrences: 2 }],
          note: "情绪持续升温",
        },
        warnings: ["宏观数据缺失"],
        notes: ["龙虎榜延迟"],
      }),
    );

    expect(markdown).toContain("# A股市场每日复盘 - 2026-10-29");
    expect(markdown).toContain("## 市场总览");
    expect(markdown).toContain("## 指数复盘");
    expect(markdown).toContain("## 机会与风险展望");
    expect(markdown).toContain("## 情绪周期定位：主升共振");
    expect(markdown).toContain("## 明日三情景预案");
    expect(markdown).toContain("## 次日观察锚点");
    expect(markdown).toContain("## 关键点位与量能阈值");
    expect(markdown).toContain("## 上一交易日复盘自检（2026-10-28 → 2026-10-29）");
    expect(markdown).toContain("- 观察标的命中率：1/2");
    expect(markdown).toContain("- 乙：次日行情缺失");
    expect(markdown).toContain("## 情绪周期历史趋势");
    expect(markdown).toContain("## 复盘数据状态");
    expect(markdown).toContain("## 数据核验警告");
    expect(markdown).toContain("## 数据说明");
  });

  it("uses the AI report section when llm_review is present", () => {
    const markdown = buildDailyReviewMarkdown(
      makeReview({ llm_review: '{"market_view":"缩量上行"}' }),
    );

    expect(markdown).toContain("## 深度复盘报告");
    expect(markdown).not.toContain("## 指数复盘");
  });

  it("skips optional sections when data is absent", () => {
    const markdown = buildDailyReviewMarkdown(makeReview());

    expect(markdown).not.toContain("## 情绪周期定位");
    expect(markdown).not.toContain("## 明日三情景预案");
    expect(markdown).not.toContain("## 上一交易日复盘自检");
    expect(markdown).not.toContain("## 数据核验警告");
  });
});
