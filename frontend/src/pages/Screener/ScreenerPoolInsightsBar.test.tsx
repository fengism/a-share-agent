import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ScreenerPoolInsightsBar from "./ScreenerPoolInsightsBar";
import type { ScreenerItem } from "../../types/stock";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

const mockItems: ScreenerItem[] = [
  {
    code: "600519",
    name: "贵州茅台",
    price: 1800,
    change_pct: 2.5,
    pe_ttm: 30,
    pb: 9,
    market_cap: 22000,
    turnover_pct: 1.2,
    volume: 100000,
    second_industry: { code: "1", name: "白酒" },
  },
  {
    code: "000858",
    name: "五粮液",
    price: 140,
    change_pct: 1.5,
    pe_ttm: 20,
    pb: 4,
    market_cap: 5500,
    turnover_pct: 2.1,
    volume: 80000,
    second_industry: { code: "1", name: "白酒" },
  },
  {
    code: "300750",
    name: "宁德时代",
    price: 260,
    change_pct: -1.2,
    pe_ttm: 25,
    pb: 5,
    market_cap: 11000,
    turnover_pct: 3.5,
    volume: 120000,
    second_industry: { code: "2", name: "电池" },
  },
];

describe("ScreenerPoolInsightsBar", () => {
  it("renders industry distribution and median indicators correctly", () => {
    const onSelect = vi.fn();
    render(
      <ScreenerPoolInsightsBar
        items={mockItems}
        total={100}
        onSelectIndustry={onSelect}
      />
    );

    expect(screen.getByText(/样本透视 \(前 3 只 \/ 总 100 只\)/)).toBeInTheDocument();
    expect(screen.getByText("白酒")).toBeInTheDocument();
    expect(screen.getByText("电池")).toBeInTheDocument();
    expect(screen.getByText(/2涨/)).toBeInTheDocument();
    expect(screen.getByText(/1跌/)).toBeInTheDocument();

    // 点击行业标签触发过滤
    fireEvent.click(screen.getByText("白酒"));
    expect(onSelect).toHaveBeenCalledWith("白酒");
  });

  it("handles AI diagnosis button click", () => {
    mockNavigate.mockClear();
    render(
      <ScreenerPoolInsightsBar
        items={mockItems}
        total={3}
      />
    );

    const btn = screen.getByRole("button", { name: /AI 诊断候选池/ });
    fireEvent.click(btn);

    expect(mockNavigate).toHaveBeenCalledWith(
      expect.stringContaining("/chat?prompt=")
    );
    expect(mockNavigate).toHaveBeenCalledWith(
      expect.stringContaining(encodeURIComponent("贵州茅台"))
    );
  });

  it("returns null when items is empty", () => {
    const { container } = render(
      <ScreenerPoolInsightsBar items={[]} total={0} />
    );
    expect(container).toBeEmptyDOMElement();
  });
});
