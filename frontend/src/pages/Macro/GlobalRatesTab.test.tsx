import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import GlobalRatesTab from "./GlobalRatesTab";

vi.mock("../../api/queries", () => ({
  useGlobalMacroRates: () => ({
    data: {
      timestamp: "2026-09-02T14:00:00Z",
      dollar_and_fx: {
        dxy: { name: "美元指数", code: "UDI", value: 99.8, change: 0.1, change_pct: 0.1 },
        usd_cnh: { name: "美元兑离岸人民币", code: "USDCNH", value: 6.72, change: 0.01, change_pct: 0.01 },
      },
      treasury_yields_and_spreads: {
        date: "2026-09-02",
        china_10y_yield: 1.68,
        china_2y_yield: 1.24,
        us_10y_yield: 4.79,
        us_2y_yield: 4.39,
        us_china_10y_spread: -3.11,
        us_china_spread_status: "中美利差倒挂（美债收益率高于中债）",
        us_10y_2y_spread: 0.4,
        us_yield_curve_status: "收益率曲线正常陡峭",
      },
      treasury_curve: {
        history: [
          {
            date: "2026-09-02",
            cn_2y: 1.24,
            cn_5y: 1.40,
            cn_10y: 1.68,
            cn_30y: 2.14,
            cn_10y_2y: 0.44,
            us_2y: 4.39,
            us_5y: 4.55,
            us_10y: 4.79,
            us_30y: 5.27,
            us_10y_2y: 0.40,
            spread_10y: -3.11,
            spread_2y: -3.15,
          },
        ],
        term_structure: [
          { tenor: "2Y", cn_yield: 1.24, us_yield: 4.39, spread: -3.15 },
          { tenor: "10Y", cn_yield: 1.68, us_yield: 4.79, spread: -3.11 },
        ],
        total_count: 1,
      },
      central_bank_policy_rates: {
        china_lpr_1y: "3.10%",
        china_lpr_5y: "3.60%",
        us_fed_funds_rate: "4.25% - 4.50%",
      },
      market_implications: {
        us_10y_impact: "美债收益率高位压制科技股估值。",
        us_china_spread_impact: "利差倒挂收窄有利于外资回流。",
      },
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

describe("GlobalRatesTab", () => {
  it("renders global macro rates, treasury yield curves and tables", () => {
    render(<GlobalRatesTab />);
    expect(screen.getByText("美元指数 (DXY)")).toBeInTheDocument();
    expect(screen.getByText("美元兑离岸人民币 (USD/CNH)")).toBeInTheDocument();
    expect(screen.getByText("美债 10 年期收益率")).toBeInTheDocument();
    expect(screen.getByText("中美国债收益率走势与利差曲线对比（参考东方财富数据中心）")).toBeInTheDocument();
    expect(screen.getByText("中美国债收益率与利差历史明细")).toBeInTheDocument();
    expect(screen.getByText("中美国债收益率期限结构对比 (2Y · 5Y · 10Y · 30Y)")).toBeInTheDocument();
  });
});
