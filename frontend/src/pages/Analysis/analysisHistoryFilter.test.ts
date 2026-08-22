import { describe, expect, it } from "vitest";
import type { AnalysisHistoryItem } from "../../types/stock";
import { filterAnalysisHistory } from "./analysisHistoryFilter";

const history: AnalysisHistoryItem[] = [
  {
    stock_code: "600519",
    stock_name: "贵州茅台",
    analysis_date: "20260813",
    current_price: 1500,
    overall_rating: 8,
    signal: "buy",
    confidence: 0.8,
    can_delete: true,
  },
  {
    stock_code: "000001",
    stock_name: "平安银行",
    analysis_date: "20260812",
    current_price: 10,
    overall_rating: 6,
    signal: "hold",
    confidence: 0.6,
    can_delete: true,
  },
];

describe("filterAnalysisHistory", () => {
  it("filters by stock code or name and ignores surrounding whitespace", () => {
    expect(filterAnalysisHistory(history, " 6005 ")).toEqual([history[0]]);
    expect(filterAnalysisHistory(history, "银行")).toEqual([history[1]]);
  });

  it("returns all history for an empty query", () => {
    expect(filterAnalysisHistory(history, "   ")).toBe(history);
  });
});
