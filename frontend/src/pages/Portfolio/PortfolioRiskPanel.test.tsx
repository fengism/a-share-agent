import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import PortfolioRiskPanel from "./PortfolioRiskPanel";

describe("PortfolioRiskPanel", () => {
  it("shows concentration metrics and actionable warnings", () => {
    render(
      <PortfolioRiskPanel risk={{
        largest_position_stock_code: "600519",
        largest_position_stock_name: "贵州茅台",
        max_single_stock_pct: 50,
        top3_concentration_pct: 95,
        concentration_level: "high",
        priced_stock_count: 4,
        unpriced_stock_count: 1,
        warnings: [
          "1 只股票缺少行情，集中度仅基于已定价持仓计算。",
          "最大持仓 贵州茅台 占比 50.00%，单股波动影响较大。",
        ],
      }} />,
    );

    expect(screen.getByText("持仓集中度")).toBeInTheDocument();
    expect(screen.getByText("高风险")).toBeInTheDocument();
    expect(screen.getByText("贵州茅台 · 600519")).toBeInTheDocument();
    expect(screen.getByText("最大单股权重").closest(".ant-statistic")).toHaveTextContent("50.00%");
    expect(screen.getByText("前三大持仓占比").closest(".ant-statistic")).toHaveTextContent("95.00%");
    expect(screen.getByText(/1 只股票缺少行情/)).toBeInTheDocument();
    expect(screen.getByText(/单股波动影响较大/)).toBeInTheDocument();
  });
});
