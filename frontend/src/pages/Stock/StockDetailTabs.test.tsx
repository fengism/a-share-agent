import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import StockDetailTabs from "./StockDetailTabs";

const mocks = vi.hoisted(() => ({
  analysis: vi.fn(),
  retry: vi.fn(),
  comments: vi.fn(),
  fundFlow: vi.fn(),
  valuation: vi.fn(),
}));

vi.mock("../../api/queries", () => ({
  useAnalysisSnapshot: (...args: unknown[]) => mocks.analysis(...args),
  useRetailSentiment: (...args: unknown[]) => mocks.comments(...args),
}));
vi.mock("../../features/investment-research/KeyFinancialMetricsSection", () => ({
  default: () => <div>关键财务指标内容</div>,
}));
vi.mock("../../features/investment-research/RevenueBreakdownSection", () => ({
  default: () => <div>营收与毛利构成</div>,
}));
vi.mock("../../features/stock-insights/AnnouncementsPanel", () => ({ default: () => <div>公告内容</div> }));
vi.mock("../../features/stock-insights/ResearchReportsPanel", () => ({ default: () => <div>研报内容</div> }));
vi.mock("../../features/stock-insights/FundFlowPanel", () => ({
  default: ({ code }: { code: string }) => {
    mocks.fundFlow(code);
    return <div>资金内容</div>;
  },
}));
vi.mock("./StockNewsPanel", () => ({ default: () => <div>新闻内容</div> }));

vi.mock("./StockValuationTab", () => ({
  default: ({ code }: { code: string }) => {
    mocks.valuation(code);
    return <div>估值详情</div>;
  },
}));

function LocationProbe() {
  return <span data-testid="search">{useLocation().search}</span>;
}

function renderTabs(entry = "/stock/600519") {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <StockDetailTabs code="600519" />
      <LocationProbe />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.analysis.mockReturnValue({
    data: { cached_analysis: { fundamental: { score: 8, summary: "盈利稳健", strengths: ["品牌优势"], risks: ["需求波动"] } } },
    isLoading: false, error: null, refetch: mocks.retry,
  });
  mocks.comments.mockReturnValue({ data: null, isLoading: false, error: null, refetch: mocks.retry });
});

describe("StockDetailTabs", () => {
  it("combines fundamentals and financial data without loading comments", () => {
    renderTabs();
    expect(screen.getByRole("tab", { name: "财务" })).toHaveAttribute("aria-selected", "true");
    for (const text of ["盈利稳健", "品牌优势", "需求波动", "营收与毛利构成", "关键财务指标内容"]) {
      expect(screen.getByText(text)).toBeVisible();
    }
    expect(mocks.analysis).toHaveBeenCalledWith("600519");
    expect(mocks.comments).not.toHaveBeenCalled();
    expect(mocks.fundFlow).not.toHaveBeenCalled();
  });

  it("loads comments only when selected in information and retains other URL params", () => {
    renderTabs("/stock/600519?from=watchlist");
    fireEvent.click(screen.getByRole("tab", { name: "资讯" }));
    expect(screen.getByText("公告内容")).toBeVisible();
    expect(mocks.comments).not.toHaveBeenCalled();
    expect(mocks.fundFlow).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("tab", { name: "相关新闻" }));
    expect(screen.getByText("新闻内容")).toBeVisible();
    fireEvent.click(screen.getByRole("tab", { name: "散户评论" }));
    expect(mocks.comments).toHaveBeenCalledWith("600519");
    expect(screen.getByText("暂无散户讨论样本")).toBeVisible();
    expect(screen.getByTestId("search")).toHaveTextContent("?from=watchlist&tab=information");
    fireEvent.click(screen.getByRole("tab", { name: "财务" }));
    expect(screen.getByText("盈利稳健")).toBeVisible();
    expect(screen.getByTestId("search")).toHaveTextContent("?from=watchlist");
  });

  it("supports opening information directly without querying fundamentals", () => {
    renderTabs("/stock/600519?tab=information");
    expect(screen.getByRole("tab", { name: "资讯" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("公告内容")).toBeVisible();
    expect(mocks.analysis).not.toHaveBeenCalled();
  });

  it("keeps fund flow beside financials and information, with on-demand loading", () => {
    renderTabs("/stock/600519?from=watchlist");
    const fundFlowTab = screen.getByRole("tab", { name: "资金流向" });
    const detailTabList = fundFlowTab.closest('[role="tablist"]') as HTMLElement;
    expect(within(detailTabList).getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["财务", "估值", "资金流向", "资讯"]);
    expect(mocks.fundFlow).not.toHaveBeenCalled();
    fireEvent.click(fundFlowTab);
    expect(fundFlowTab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("heading", { name: "资金流向" })).toBeVisible();
    expect(screen.getByText("资金内容")).toBeVisible();
    expect(mocks.fundFlow).toHaveBeenCalledWith("600519");
    expect(screen.getByTestId("search")).toHaveTextContent("?from=watchlist&tab=fund-flow");

    fireEvent.click(screen.getByRole("tab", { name: "资讯" }));
    const newsTabs = screen.getByRole("tab", { name: "公司公告" }).closest('[role="tablist"]') as HTMLElement;
    expect(within(newsTabs).queryByRole("tab", { name: "资金流向" })).not.toBeInTheDocument();
    expect(within(newsTabs).getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["公司公告", "券商研报", "相关新闻", "散户评论"]);
    expect(screen.queryByText("资金内容")).not.toBeInTheDocument();
    expect(screen.getByTestId("search")).toHaveTextContent("?from=watchlist&tab=information");
  });

  it("opens fund flow directly without querying fundamentals or comments", () => {
    renderTabs("/stock/600519?tab=fund-flow");
    expect(screen.getByRole("tab", { name: "资金流向" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("资金内容")).toBeVisible();
    expect(mocks.fundFlow).toHaveBeenCalledWith("600519");
    expect(mocks.analysis).not.toHaveBeenCalled();
    expect(mocks.comments).not.toHaveBeenCalled();
  });

  it("loads valuation on demand in its own top-level tab", () => {
    renderTabs("/stock/600519?from=watchlist");
    expect(mocks.valuation).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("tab", { name: "估值" }));
    expect(screen.getByText("估值详情")).toBeVisible();
    expect(mocks.valuation).toHaveBeenCalledWith("600519");
    expect(screen.getByTestId("search")).toHaveTextContent("?from=watchlist&tab=valuation");
    expect(mocks.comments).not.toHaveBeenCalled();
    expect(mocks.fundFlow).not.toHaveBeenCalled();
  });

  it("opens the valuation tab directly", () => {
    renderTabs("/stock/600519?tab=valuation");
    expect(screen.getByRole("tab", { name: "估值" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("估值详情")).toBeVisible();
    expect(mocks.analysis).not.toHaveBeenCalled();
  });

  it("falls back to financials for invalid tab links", () => {
    renderTabs("/stock/600519?tab=unknown");
    expect(screen.getByRole("tab", { name: "财务" })).toHaveAttribute("aria-selected", "true");
  });

  it("keeps financial facts visible if no AI analysis exists", () => {
    mocks.analysis.mockReturnValue({ data: { cached_analysis: null }, isLoading: false, error: null });
    renderTabs();
    expect(screen.queryByRole("region", { name: "基本面概览" })).not.toBeInTheDocument();
    expect(screen.getByText("营收与毛利构成")).toBeVisible();
    expect(screen.getByText("关键财务指标内容")).toBeVisible();
  });

  it("isolates failed analysis from financial data and supports retry", () => {
    mocks.analysis.mockReturnValue({ isLoading: false, error: new Error("snapshot unavailable"), refetch: mocks.retry });
    renderTabs();
    expect(screen.getByText("基本面摘要加载失败")).toBeVisible();
    expect(screen.getByText("关键财务指标内容")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /重\s*试/ }));
    expect(mocks.retry).toHaveBeenCalledOnce();
  });
});
