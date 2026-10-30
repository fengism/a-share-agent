import { describe, expect, it } from "vitest";
import type { ScreenerItem } from "../../types/stock";
import { generateScreenerCsv } from "./exportCsv";

describe("exportCsv", () => {
  const mockItems: ScreenerItem[] = [
    {
      code: "600519",
      name: "贵州茅台",
      price: 1500.5,
      change_pct: 1.25,
      pe_ttm: 25.4,
      pb: 8.6,
      market_cap: 18000,
      turnover_pct: 0.5,
      volume: 1000000,
      board: "主板",
      exchange: "SH",
      first_industry: { code: "801120", name: "食品饮料" },
      second_industry: { code: "801123", name: "白酒Ⅱ" },
      concepts: ["消费白马", "MSCI中国"],
      exchange_industry: "制造业",
    },
    {
      code: "000001",
      name: '平安"银行',
      price: 10.2,
      change_pct: -0.5,
      pe_ttm: 5.1,
      pb: 0.6,
      market_cap: 2000,
      turnover_pct: 1.2,
      volume: 500000,
      board: "主板",
      exchange: "SZ",
      second_industry: { code: "801780", name: "银行" },
      concepts: ["金融科技,跨境支付"],
      exchange_industry: "金融业",
    },
  ];

  it("generates standard CSV with UTF-8 BOM and correct headers", () => {
    const csv = generateScreenerCsv({ items: mockItems });
    expect(csv.startsWith("\uFEFF")).toBe(true);

    const lines = csv.replace("\uFEFF", "").split("\r\n");
    expect(lines.length).toBe(3); // header + 2 items
    expect(lines[0]).toBe("代码,名称,市场,综合评分,现价,涨跌幅(%),PE(TTM),PB,总市值(亿),换手率(%),振幅(%),量比,60日涨幅(%),成交量,申万行业,概念题材,交易所行业");

    expect(lines[1]).toContain("600519,贵州茅台,主板,,1500.50,1.25,25.40,8.60,18000.00,0.50,,,,1000000,食品饮料 / 白酒Ⅱ,消费白马 · MSCI中国,制造业");
    // Quotes and commas escaping
    expect(lines[2]).toContain('"平安""银行"');
    expect(lines[2]).toContain('"金融科技,跨境支付"');
  });

  it("includes strategy columns when strategy metrics are present", () => {
    const strategySignalDates = new Map([["600519", "2026-09-01"]]);
    const strategySignalAges = new Map([["600519", 5]]);
    const strategyReturnsSinceSignal = new Map([["600519", 8.2]]);
    const strategyAverageAmounts = new Map([["600519", 35.6]]);

    const csv = generateScreenerCsv({
      items: [mockItems[0]],
      strategySignalDates,
      strategySignalAges,
      strategyReturnsSinceSignal,
      strategyAverageAmounts,
    });

    const lines = csv.replace("\uFEFF", "").split("\r\n");
    expect(lines[0]).toContain("策略信号日,信号年龄(根),信号后收益(%),20日均成交额(亿)");
    expect(lines[1]).toContain("2026-09-01,5,8.20,35.60");
  });

  it("includes percentile columns when showPercentile is true", () => {
    const percentileMap = new Map([
      ["600519", 20],
      ["600519_pb", 45],
    ]);

    const csv = generateScreenerCsv({
      items: [mockItems[0]],
      percentileMap,
      showPercentile: true,
    });

    const lines = csv.replace("\uFEFF", "").split("\r\n");
    expect(lines[0]).toContain("PE分位(%),PB分位(%)");
    expect(lines[1]).toContain("20,45");
  });
});
