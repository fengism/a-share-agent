import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import StockSnapshotModal from "./StockSnapshotModal";

describe("StockSnapshotModal", () => {
  it("renders stock snapshot card with price, tape and 52-week range", () => {
    const onClose = vi.fn();
    render(
      <StockSnapshotModal
        open={true}
        onClose={onClose}
        info={{
          code: "600519",
          name: "贵州茅台",
          current_price: 1800.5,
          first_industry: { code: "B", name: "白酒" },
          concepts: [{ code: "C1", name: "消费龙头" }],
          market_cap: 2260000000000,
          pe_ttm: 28.5,
          pb: 8.2,
          turnover_pct: 0.45,
        }}
        changePct={1.25}
        tape={{
          open: 1790.0,
          high: 1815.0,
          low: 1788.0,
          prevClose: 1778.0,
          amount: 3500000000,
          amplitude: 1.52,
          fiftyTwoWeekLow: 1350.0,
          fiftyTwoWeekHigh: 1920.0,
        }}
      />,
    );

    expect(screen.getByText("导出个股速览卡片")).toBeInTheDocument();
    expect(screen.getByText("A-Share Agent · 智能投研")).toBeInTheDocument();
    expect(screen.getByText("贵州茅台")).toBeInTheDocument();
    expect(screen.getByText("600519")).toBeInTheDocument();
    expect(screen.getByText("¥1800.50")).toBeInTheDocument();
    expect(screen.getByText("+1.25% · 换手 0.45%")).toBeInTheDocument();
    expect(screen.getByText("52周区间")).toBeInTheDocument();
    expect(screen.getByText("1,350.00")).toBeInTheDocument();
    expect(screen.getByText("1,920.00")).toBeInTheDocument();
    expect(screen.getByText("2.26万亿")).toBeInTheDocument();
    expect(screen.getByText("28.50")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /保存图片/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /复制卡片图片/ })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /关\s*闭/ }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
