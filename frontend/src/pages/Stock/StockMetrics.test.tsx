import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import StockMetrics from "./StockMetrics";

vi.mock("../../api/queries", () => ({
  useAnalysisSnapshot: () => ({ data: { cached_analysis: null }, isLoading: false, error: null, refetch: vi.fn() }),
}));

const INFO = {
  code: "600519",
  name: "贵州茅台",
  listing_date: "2001-08-27",
  total_shares: 1_256_197_800,
  circulating_shares: 1_256_197_800,
  pe_ttm: 22.35,
  pe_static: 23.18,
  pb: 7.8,
  market_cap: 1_900_000_000_000,
  float_market_cap: 1_880_000_000_000,
  turnover_pct: 0.42,
} as never;

describe("StockMetrics", () => {
  it("renders every metric label with formatted values when data is present", () => {
    render(
      <MemoryRouter>
        <StockMetrics info={INFO} />
      </MemoryRouter>,
    );

    expect(screen.getByText("总市值")).toBeInTheDocument();
    expect(screen.getByText("1.90万亿")).toBeInTheDocument();
    expect(screen.getByText("市盈率 TTM")).toBeInTheDocument();
    expect(screen.getByText("22.35")).toBeInTheDocument();
    expect(screen.getByText("上市日期")).toBeInTheDocument();
    expect(screen.getByText("2001-08-27")).toBeInTheDocument();
  });

  /**
   * 回归测试：概览网格是双列（minmax(520px,1.18fr) / minmax(360px,0.82fr)）。
   * 数据未到时若整张卡片不渲染，兄弟卡片会先占宽列、数据到达后被挤到窄列，
   * 文本重排把整页往下推（实测 CLS 0.28）。缺省时必须仍渲染完整网格。
   */
  it("keeps the same metric grid when data is not loaded yet", () => {
    render(
      <MemoryRouter>
        <StockMetrics />
      </MemoryRouter>,
    );

    // 标签是静态的，先于数据出现，用户立刻能看到卡片结构
    ["总市值", "流通市值", "总股本", "流通股本", "市盈率 TTM", "静态市盈率", "市净率", "换手率", "上市日期"].forEach(
      (label) => expect(screen.getByText(label)).toBeInTheDocument(),
    );

    // 占位骨架不能被当成真实数据读出来
    expect(screen.queryByText("1.90万亿")).not.toBeInTheDocument();
    const grid = document.querySelector(".stock-metrics-grid");
    expect(grid).toHaveAttribute("aria-busy", "true");
    // 9 个指标位都要有占位，保证与加载后几何一致
    expect(document.querySelectorAll(".stock-metric__placeholder")).toHaveLength(9);
  });
});