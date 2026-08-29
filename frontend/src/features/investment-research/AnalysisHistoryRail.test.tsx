import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import AnalysisHistoryRail from "./AnalysisHistoryRail";

const { useInfiniteAllAnalysisHistory, refetch } = vi.hoisted(() => ({
  useInfiniteAllAnalysisHistory: vi.fn(),
  refetch: vi.fn(),
}));
vi.mock("../../api/queries", () => ({ useInfiniteAllAnalysisHistory }));

const items = [{
  stock_code: "600519",
  stock_name: "贵州茅台",
  analysis_date: "2026-08-26",
  current_price: 1500,
  overall_rating: 8,
  signal: "buy",
  confidence: 0.8,
  can_delete: true,
}, {
  stock_code: "600519",
  stock_name: "贵州茅台",
  analysis_date: "2026-08-20",
  current_price: 1480,
  overall_rating: 7,
  signal: "hold",
  confidence: 0.7,
  can_delete: true,
}];

describe("AnalysisHistoryRail", () => {
  it("supports standalone links and marks only the displayed date active", () => {
    useInfiniteAllAnalysisHistory.mockReturnValue({ data: { pages: [items] }, isLoading: false, isError: false });
    render(
      <MemoryRouter>
        <AnalysisHistoryRail
          currentCode="600519"
          currentDate="20260826"
          buildHistoryUrl={(code, date) => `/investment-research/${code}?date=${date.replace(/-/g, "")}`}
          allHistoryTarget="/investment-research"
          embedded
        />
      </MemoryRouter>,
    );

    expect(useInfiniteAllAnalysisHistory).toHaveBeenCalledWith(8);
    const reportLinks = screen.getAllByRole("link", { name: /贵州茅台/ });
    expect(reportLinks[0]).toHaveAttribute("href", "/investment-research/600519?date=20260826");
    expect(reportLinks.filter((link) => link.hasAttribute("aria-current"))).toHaveLength(1);
    expect(screen.getByRole("link", { name: "查看全部分析记录" }))
      .toHaveAttribute("href", "/investment-research");
  });

  it("does not mark every same-code record active without a displayed date", () => {
    useInfiniteAllAnalysisHistory.mockReturnValue({ data: { pages: [items] }, isLoading: false, isError: false });
    render(
      <MemoryRouter>
        <AnalysisHistoryRail currentCode="600519" embedded />
      </MemoryRouter>,
    );

    expect(screen.queryAllByRole("link").filter((link) => link.hasAttribute("aria-current"))).toHaveLength(0);
  });

  it("shows a retry action for initial history errors", () => {
    useInfiniteAllAnalysisHistory.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
      refetch,
    });
    render(<MemoryRouter><AnalysisHistoryRail embedded /></MemoryRouter>);

    expect(screen.getByRole("alert")).toHaveTextContent("最近分析加载失败");
    screen.getByRole("button", { name: /重\s*试/ }).click();
    expect(refetch).toHaveBeenCalledOnce();
  });
});
