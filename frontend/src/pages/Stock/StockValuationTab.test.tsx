import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import StockValuationTab from "./StockValuationTab";

const mocks = vi.hoisted(() => ({ latest: vi.fn(), history: vi.fn(), panel: vi.fn() }));
vi.mock("../../api/queries", () => ({
  useAnalysisSnapshot: mocks.latest,
  useAnalysisHistorySnapshot: mocks.history,
}));
vi.mock("../../features/investment-research/ValuationPanel", () => ({
  default: ({ code }: { code: string }) => {
    mocks.panel(code);
    return <div>估值方法内容</div>;
  },
}));
function renderValuation(entry = "/stock/600519?tab=valuation") {
  return render(<MemoryRouter initialEntries={[entry]}><StockValuationTab code="600519" /></MemoryRouter>);
}
beforeEach(() => { vi.clearAllMocks(); });

describe("StockValuationTab", () => {
  it("shows valuation without fetching obsolete analysis scores", async () => {
    renderValuation();
    expect(screen.getByRole("heading", { name: "估值分析" })).toBeVisible();
    expect(await screen.findByText("估值方法内容")).toBeVisible();
    expect(mocks.panel).toHaveBeenCalledWith("600519");
    expect(mocks.latest).not.toHaveBeenCalled();
    expect(mocks.history).not.toHaveBeenCalled();
    expect(screen.queryByText(/分析评分/)).not.toBeInTheDocument();
  });
  it("clarifies that historical report links still show current valuation data", async () => {
    renderValuation("/stock/600519?tab=valuation&date=2026-08-20");
    expect(await screen.findByText("估值方法内容")).toBeVisible();
    expect(screen.getByText("来自 2026-08-20 的历史报告；以下估值为最新可用数据，并非历史快照")).toBeVisible();
    expect(mocks.latest).not.toHaveBeenCalled();
    expect(mocks.history).not.toHaveBeenCalled();
  });
  it("does not claim historical context for invalid dates", async () => {
    renderValuation("/stock/600519?tab=valuation&date=20260231");
    expect(await screen.findByText("估值方法内容")).toBeVisible();
    expect(screen.queryByText(/历史报告/)).not.toBeInTheDocument();
  });
});
