import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import MonthlyReturnsHeatmap from "./MonthlyReturnsHeatmap";

describe("MonthlyReturnsHeatmap", () => {
  it("renders empty state when monthly returns are empty", () => {
    render(<MonthlyReturnsHeatmap monthlyReturns={[]} />);
    expect(screen.getByText("暂无月度收益")).toBeInTheDocument();
  });

  it("renders heatmap matrix with years and monthly returns", () => {
    const data = [
      { month: "2025-01", return_pct: 3.5 },
      { month: "2025-02", return_pct: -2.1 },
      { month: "2025-03", return_pct: 4.0 },
      { month: "2026-01", return_pct: 1.5 },
    ];
    render(<MonthlyReturnsHeatmap monthlyReturns={data} />);

    expect(screen.getByText("月度收益分布")).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "月度收益热力矩阵" })).toBeInTheDocument();
    expect(screen.getByText("2025")).toBeInTheDocument();
    expect(screen.getByText("2026")).toBeInTheDocument();
    expect(screen.getByText("+3.5%")).toBeInTheDocument();
    expect(screen.getByText("-2.1%")).toBeInTheDocument();
    expect(screen.getByText("+1.5%")).toBeInTheDocument();
  });

  it("switches to list view and shows monthly items", () => {
    const data = [
      { month: "2025-01", return_pct: 3.5 },
      { month: "2026-01", return_pct: 1.5 },
    ];
    render(<MonthlyReturnsHeatmap monthlyReturns={data} />);

    fireEvent.click(screen.getByText("明细列表"));

    expect(screen.getByText("月份")).toBeInTheDocument();
    expect(screen.getByText("收益率")).toBeInTheDocument();
    expect(screen.getByText("2025-01")).toBeInTheDocument();
    expect(screen.getByText("2026-01")).toBeInTheDocument();
  });
});
