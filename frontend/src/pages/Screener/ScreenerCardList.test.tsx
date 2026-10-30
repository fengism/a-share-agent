import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import ScreenerCardList from "./ScreenerCardList";
import type { ScreenerItem, ScreenerResult } from "../../types/stock";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", () => ({
  useNavigate: () => mockNavigate,
}));

const mockItems: ScreenerItem[] = [
  {
    code: "600519",
    name: "贵州茅台",
    price: 1800,
    change_pct: 10.0,
    pe_ttm: 30,
    pb: 9,
    market_cap: 22000,
    turnover_pct: 8.5,
    volume: 100000,
    volume_ratio: 2.2,
    second_industry: { code: "1", name: "白酒" },
    concepts: ["核心资产", "MSCI中国"],
  },
];

const mockResult: ScreenerResult = {
  items: mockItems,
  total: 1,
  page: 1,
  page_size: 50,
};

describe("ScreenerCardList", () => {
  it("renders stock card details, anomaly tags, and pagination", () => {
    const onSelectCodes = vi.fn();
    const onPageChange = vi.fn();

    render(
      <ScreenerCardList
        data={mockResult}
        isLoading={false}
        selectedCodes={[]}
        onSelectedCodesChange={onSelectCodes}
        onPageChange={onPageChange}
      />
    );

    expect(screen.getByText("贵州茅台")).toBeInTheDocument();
    expect(screen.getByText("600519")).toBeInTheDocument();
    expect(screen.getByText("涨停")).toBeInTheDocument();
    expect(screen.getByText("高换手")).toBeInTheDocument();
    expect(screen.getByText("放量")).toBeInTheDocument();
    expect(screen.getByText("白酒")).toBeInTheDocument();
    expect(screen.getByText("核心资产 +1")).toBeInTheDocument();

    // 勾选操作
    const checkbox = screen.getByRole("checkbox");
    fireEvent.click(checkbox);
    expect(onSelectCodes).toHaveBeenCalledWith(["600519"]);
  });

  it("handles AI diagnosis click", () => {
    mockNavigate.mockClear();
    render(
      <ScreenerCardList
        data={mockResult}
        isLoading={false}
        selectedCodes={[]}
        onSelectedCodesChange={vi.fn()}
        onPageChange={vi.fn()}
      />
    );

    const aiBtn = screen.getByRole("button", { name: /AI 体检/ });
    fireEvent.click(aiBtn);
    expect(mockNavigate).toHaveBeenCalledWith(
      expect.stringContaining("/chat?prompt=")
    );
  });

  it("renders empty state when items is empty", () => {
    render(
      <ScreenerCardList
        data={{ items: [], total: 0, page: 1, page_size: 50 }}
        isLoading={false}
        selectedCodes={[]}
        onSelectedCodesChange={vi.fn()}
        onPageChange={vi.fn()}
      />
    );

    expect(screen.getByText("无匹配股票，请调整筛选条件")).toBeInTheDocument();
  });
});
