import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import FundamentalPanel from "./FundamentalPanel";

const financialData = {
  balance: [{
    REPORT_DATE: "2026-06-30",
    TOTAL_ASSETS: 500,
    TOTAL_LIABILITIES: 200,
    MONETARYFUNDS: 80,
    INVENTORY: 40,
    TOTAL_CURRENT_ASSETS: 180,
    TOTAL_CURRENT_LIAB: 90,
    RAW_BALANCE_FIELD: 999,
  }],
  profit: [{
    REPORT_DATE: "2026-06-30",
    OPERATE_INCOME: 200,
    OPERATE_INCOME_YOY: 12.5,
    OPERATE_COST: 120,
    PARENT_NETPROFIT: 50,
    PARENT_NETPROFIT_YOY: 8.5,
    DEDUCT_PARENT_NETPROFIT: 45,
    DEDUCT_PARENT_NETPROFIT_YOY: 7.5,
    BASIC_EPS: 1.25,
    RAW_PROFIT_FIELD: 999,
  }],
  cashflow: [{
    REPORT_DATE: "2026-06-30",
    NETCASH_OPERATE: 75,
    NETCASH_OPERATE_YOY: 15,
    NETCASH_INVEST: -20,
    RAW_CASH_FIELD: 999,
  }],
};

vi.mock("../../api/queries", () => ({
  useFinancial: (_code: string, type: keyof typeof financialData) => ({
    data: financialData[type],
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useRevenueBreakdown: () => ({
    data: {
      code: "600519",
      symbol: "sh600519",
      name: "",
      source: "sina",
      amount_unit: "CNY_yuan",
      amount_unit_inferred: true,
      by_product: [],
      by_business: [],
      by_region: [],
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

describe("FundamentalPanel key financial metrics", () => {
  it("leaves raw key financial metrics on the stock profile during normal browsing", () => {
    render(<FundamentalPanel code="600519" />);

    expect(screen.queryByText("关键财务指标")).not.toBeInTheDocument();
    expect(screen.queryByText("盈利与增长")).not.toBeInTheDocument();
    expect(screen.queryByText("营业收入")).not.toBeInTheDocument();
  });

  it("renders all groups in one key-metrics PDF section", () => {
    render(<FundamentalPanel code="600519" isExportingPdf />);

    expect(screen.getByText("关键财务指标")).toBeInTheDocument();
    expect(screen.getAllByText("盈利与增长").length).toBeGreaterThan(0);
    expect(screen.getAllByText("资产健康").length).toBeGreaterThan(0);
    expect(screen.getAllByText("现金质量").length).toBeGreaterThan(0);
    expect(screen.getByText("毛利率")).toBeInTheDocument();
    expect(screen.getByText("流动比率")).toBeInTheDocument();
    expect(screen.getByText("现金利润比")).toBeInTheDocument();

    const sections = screen.getAllByTestId("pdf-key-financial-metrics");
    expect(sections).toHaveLength(1);
    expect(sections[0]).toHaveAttribute("data-pdf-row-count", "19");
  });
});
