import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PortfolioRiskPanel from "./PortfolioRiskPanel";

describe("PortfolioRiskPanel", () => {
  it("shows concentration metrics and actionable warnings", () => {
    const onUseSuggestion = vi.fn();
    render(
      <PortfolioRiskPanel onUseSuggestion={onUseSuggestion} risk={{
        largest_position_stock_code: "600519",
        largest_position_stock_name: "贵州茅台",
        max_single_stock_pct: 50,
        top3_concentration_pct: 95,
        top5_concentration_pct: 100,
        remaining_add_capacity: 12000,
        concentration_index: 4200,
        effective_holding_count: 2.38,
        securities_top5_concentration_pct: 98.5,
        securities_concentration_index: 5100,
        securities_effective_holding_count: 1.96,
        cash_pct: 12.5,
        concentration_level: "high",
        priced_stock_count: 4,
        unpriced_stock_count: 1,
        max_total_position_limit_pct: 80,
        max_single_stock_limit_pct: 30,
        max_sector_limit_pct: 40,
        largest_sector_name: "食品饮料",
        largest_sector_pct: 55,
        sector_allocations: [{
          sector_name: "食品饮料",
          market_value: 55000,
          allocation_pct: 55,
          stock_codes: ["600519"],
        }],
        trim_suggestions: [{
          stock_code: "600519",
          stock_name: "贵州茅台",
          sector_name: "食品饮料",
          current_pct: 50,
          target_pct: 30,
          suggested_shares: 100,
          sellable_shares: 100,
          estimated_amount: 16000,
          lot_size: 100,
          reasons: ["单股仓位 50.00% 超过上限 30.00%"],
        }],
        warnings: [
          "1 只股票缺少行情，集中度仅基于已定价持仓计算。",
          "最大持仓 贵州茅台 占比 50.00%，单股波动影响较大。",
        ],
      }} />,
    );

    expect(screen.getByText("仓位风险")).toBeInTheDocument();
    expect(screen.getByText("高风险")).toBeInTheDocument();
    expect(screen.getByText("贵州茅台 · 600519")).toBeInTheDocument();
    expect(screen.getByText("最大单股权重").closest(".ant-statistic")).toHaveTextContent("50.00%");
    expect(screen.getByText("前三大持仓占比").closest(".ant-statistic")).toHaveTextContent("95.00%");
    expect(screen.getByText("总仓位上限").closest(".ant-statistic")).toHaveTextContent("80.00%");
    expect(screen.getByText(/剩余可加仓 ¥12,000.00/)).toBeInTheDocument();
    expect(screen.getByText("最大行业仓位").closest(".ant-statistic")).toHaveTextContent("55.00%");
    expect(screen.getByText("前五大持仓（含现金）").closest(".ant-statistic")).toHaveTextContent("100.00%");
    expect(screen.getByText("有效持仓数（含现金）").closest(".ant-statistic")).toHaveTextContent("2.38");
    expect(screen.getByText("集中度 HHI（含现金）").closest(".ant-statistic")).toHaveTextContent("4,200.00");
    expect(screen.getByText("证券前五大占比").closest(".ant-statistic")).toHaveTextContent("98.50%");
    expect(screen.getByText("证券有效持仓数").closest(".ant-statistic")).toHaveTextContent("1.96");
    expect(screen.getByText("证券 HHI").closest(".ant-statistic")).toHaveTextContent("5,100.00");
    expect(screen.getByText("现金占比").closest(".ant-statistic")).toHaveTextContent("12.50%");
    expect(screen.getByText("减仓建议")).toBeInTheDocument();
    expect(screen.getByText(/卖出 100 股/)).toBeInTheDocument();
    expect(screen.getByText(/单股仓位 50.00% 超过上限 30.00%/)).toBeInTheDocument();
    expect(screen.getByText(/食品饮料 55.00%/)).toBeInTheDocument();
    expect(screen.getByText(/1 只股票缺少行情/)).toBeInTheDocument();
    expect(screen.getByText(/单股波动影响较大/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "预填卖出" }));
    expect(onUseSuggestion).toHaveBeenCalledWith(expect.objectContaining({
      stock_code: "600519",
      suggested_shares: 100,
    }));
  });
});
