import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type {
  DCFValuationResult,
  StockValuationDetail,
  ValuationMethodResult,
} from "../../types/stock";
import ValuationPanel from "./ValuationPanel";

function method(
  name: string,
  perShareValue: number,
  dataQualityScore: number,
): ValuationMethodResult {
  return {
    method: name,
    available: true,
    target_multiple: 20,
    equity_value: perShareValue * 100,
    per_share_value: perShareValue,
    upside_pct: 10,
    confidence: "medium",
    confidence_score: 0.75,
    data_quality_score: dataQualityScore,
    weight: 0.2,
    value_range: [perShareValue * 0.9, perShareValue * 1.1],
    applicability: "适用于当前盈利结构",
    basis: "同行中位数",
    reason: null,
  };
}

const dcf: DCFValuationResult = {
  method: "dcf",
  available: true,
  base_cashflow: 800,
  discount_rate: 0.1,
  terminal_growth_rate: 0.03,
  forecast_years: 5,
  equity_value: 12_000,
  per_share_value: 120,
  upside_pct: 20,
  confidence: "high",
  confidence_score: 0.85,
  data_quality_score: 0.88,
  weight: 0.2,
  value_range: [100, 140],
  applicability: "现金流稳定",
  basis: "经营现金流减资本开支",
  reason: null,
  fcfe_source: "reported_fcfe",
  scenarios: [
    {
      name: "bear",
      label: "悲观",
      growth_rate: 0.03,
      discount_rate: 0.11,
      terminal_growth_rate: 0.02,
      equity_value: 9_000,
      per_share_value: 90,
      upside_pct: -10,
    },
    {
      name: "base",
      label: "基准",
      growth_rate: 0.06,
      discount_rate: 0.1,
      terminal_growth_rate: 0.03,
      equity_value: 12_000,
      per_share_value: 120,
      upside_pct: 20,
    },
    {
      name: "bull",
      label: "乐观",
      growth_rate: 0.09,
      discount_rate: 0.09,
      terminal_growth_rate: 0.04,
      equity_value: 15_000,
      per_share_value: 150,
      upside_pct: 50,
    },
  ],
  sensitivity: [
    { discount_rate: 0.09, terminal_growth_rate: 0.02, per_share_value: 110 },
    { discount_rate: 0.09, terminal_growth_rate: 0.03, per_share_value: 120 },
    { discount_rate: 0.1, terminal_growth_rate: 0.02, per_share_value: 100 },
    { discount_rate: 0.1, terminal_growth_rate: 0.03, per_share_value: 110 },
  ],
  reverse_dcf: {
    available: true,
    implied_growth_rate: 0.055,
    market_equity_value: 10_000,
    reason: null,
  },
};

const detail: StockValuationDetail = {
  code: "600519",
  report_date: "2026-06-30",
  current_price: 100,
  market_cap: 10_000,
  total_shares: 100,
  industry: "白酒",
  multiples: { pe_ttm: 20, pb: 6, ps_ttm: 8, peg: 1.5 },
  percentiles: { pe_3y: 40, pb_3y: 50, ps_3y: 60 },
  fundamentals: {
    revenue: 5_000,
    revenue_yoy: 8,
    net_profit: 1_000,
    net_profit_yoy: 10,
    non_net_profit: 950,
    non_net_profit_yoy: 9,
    shareholders_equity: 4_000,
    operating_cashflow: 1_200,
    capital_expenditure: 300,
  },
  peer_summary: {
    pe_median: 22,
    pb_median: 5.5,
    ps_median: 7.5,
    peer_count: 5,
    peers: [
      { name: "同行公司", code: "000001", pe_ttm: 22, pb: 5.5, ps_ttm: 7.5 },
    ],
    pe_stats: { sample_size: 4, excluded_count: 1, confidence_score: 0.8 },
    pb_stats: { sample_size: 5, excluded_count: 0, confidence_score: 1 },
    ps_stats: { sample_size: 3, excluded_count: 2, confidence_score: 0.6 },
  },
  fair_values: {
    pe: method("pe", 110, 0.9),
    pb: method("pb", 105, 0.85),
    ps: method("ps", 115, 0.8),
    peg: method("peg", 125, 0.75),
    dcf,
  },
  blended_fair_value: 115,
  fair_value_range: [100, 130],
  valuation_view: "低估",
  valuation_summary: "多方法估值显示当前价格具备安全边际。",
  profile: { category: "growth", label: "稳健成长", rationale: ["盈利稳定"] },
  method_weights: { pe: 0.2, pb: 0.2, ps: 0.2, peg: 0.2, dcf: 0.2 },
  data_quality: {
    score: 0.9,
    grade: "high",
    ttm_source: "reported_ttm",
    cashflow_source: "reported_fcfe",
    peer_confidence: 0.8,
    limitations: ["同行样本仍需结合业务可比性判断。"],
  },
  notes: [],
  institution_forecasts: [],
};

const mocks = vi.hoisted(() => ({ query: vi.fn() }));
vi.mock("../../api/queries", () => ({ useValuationDetail: () => mocks.query() }));
beforeEach(() => {
  mocks.query.mockReturnValue({ data: detail, isLoading: false, error: null, refetch: vi.fn() });
});

describe("ValuationPanel", () => {
  it("shows a full-width snapshot without the dimension label or score column", () => {
    render(<ValuationPanel code="600519" />);
    const snapshot = screen.getByRole("region", { name: "当前估值快照" });
    expect(within(snapshot).getByText("PE(TTM)")).toBeVisible();
    expect(within(snapshot).getByText("股票画像")).toBeVisible();
    expect(screen.queryByText("估值面")).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "估值面评分" })).not.toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("uses consistent card structure for all five methods without dropping long explanations", () => {
    const reason = "缺少有效同行样本，当前方法不可用，请结合其他估值结果和风险说明。";
    mocks.query.mockReturnValue({ data: { ...detail, fair_values: {
      ...detail.fair_values,
      pb: { ...method("pb", 105, 0), available: false, reason },
    } } });
    render(<ValuationPanel code="600519" />);
    const methods = screen.getAllByRole("article");
    expect(methods).toHaveLength(5);
    expect(methods[0].parentElement).toHaveClass("valuation-method-grid");
    for (const [index, title] of ["PE 估值法", "PB 估值法", "PS 估值法", "PEG 估值法", "DCF 估值法"].entries()) {
      expect(methods[index]).toHaveClass("valuation-method-card");
      expect(within(methods[index]).getByRole("heading", { name: title })).toHaveClass("valuation-method-card__title");
      expect(methods[index].querySelector(".valuation-method-card__value")).toBeInTheDocument();
      expect(methods[index].querySelector(".valuation-method-card__tags")).toBeInTheDocument();
    }
    expect(within(methods[1]).getByText("不可用")).toBeVisible();
    expect(within(methods[1]).getByText(reason)).toBeVisible();
    expect(within(methods[0]).getByText("¥110.00")).toBeVisible();
  });

  it("renders quality-aware DCF analysis and peer sample diagnostics", () => {
    render(<ValuationPanel code="600519" />);

    expect(screen.getByText("数据质量")).toBeInTheDocument();
    expect(screen.getByText("高 · 90%")).toBeInTheDocument();
    expect(screen.getByText("悲观")).toBeInTheDocument();
    expect(screen.getByText("基准")).toBeInTheDocument();
    expect(screen.getByText("乐观")).toBeInTheDocument();
    expect(screen.getByText("每股价值敏感性")).toBeInTheDocument();
    expect(screen.getByText("反向 DCF")).toBeInTheDocument();
    expect(screen.getByText(/当前价格隐含未来五年初始增长率 5\.5%/)).toBeInTheDocument();
    expect(screen.getByText("资本开支")).toBeInTheDocument();
    expect(screen.getByText("PE 有效 / 剔除")).toBeInTheDocument();
    expect(screen.getByText("4 / 1")).toBeInTheDocument();
  });
});
