import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { StockReportPage } from "../../types/stock";
import ResearchReportsPanel from "../../features/stock-insights/ResearchReportsPanel";

const useStockReportsMock = vi.fn();

vi.mock("../../api/queries", () => ({
  useStockReports: (...args: unknown[]) => useStockReportsMock(...args),
}));

function mockQuery(data: StockReportPage | undefined, isLoading = false, error: unknown = null) {
  useStockReportsMock.mockReturnValue({
    data,
    isLoading,
    error,
    refetch: vi.fn(),
  });
}

const reportPage: StockReportPage = {
  code: "002273",
  months: 6,
  total_count: 2,
  items: [
    {
      id: "841201564931",
      title: "水晶光电(002273)：主业营收&毛利率稳健向上 AI光学打造新增长极",
      org: "中泰证券",
      author: "王芳/杨旭",
      date: "2026-08-27",
      rating: "买入",
      goal_price: null,
      report_type: "公司",
      url: "http://stock.finance.sina.com.cn/stock/view/paper.php?reportid=841201564931",
      source: "sina_stock_reports",
      source_api: "ReportService.getList",
    },
    {
      id: "838608343934",
      title: "水晶光电(002273)：业务基本盘稳固 AI光学打开成长空间",
      org: "东方证券",
      author: "蒯剑",
      date: "2026-07-28",
      rating: "增持",
      goal_price: 33.28,
      report_type: "公司",
      url: "",
      source: "sina_stock_reports",
      source_api: "ReportService.getList",
    },
  ],
};

describe("ResearchReportsPanel", () => {
  it("renders recent-half-year reports as a table with rating and goal price", () => {
    mockQuery(reportPage);
    render(<ResearchReportsPanel code="002273" />);

    expect(useStockReportsMock).toHaveBeenCalledWith("002273");
    const table = screen.getByRole("table");
    for (const header of ["日期", "评级", "目标价", "券商", "研报标题"]) {
      expect(within(table).getByRole("columnheader", { name: header })).toBeInTheDocument();
    }
    expect(within(table).getAllByRole("row")).toHaveLength(3); // 表头 + 2 行数据
    expect(screen.getByRole("link", { name: "水晶光电(002273)：主业营收&毛利率稳健向上 AI光学打造新增长极" }))
      .toHaveAttribute("href", reportPage.items[0].url);
    expect(screen.getByText("买入")).toBeInTheDocument();
    expect(screen.getByText("33.28")).toBeInTheDocument();
    expect(screen.getByText(/最近 6 个月/)).toBeInTheDocument();
    expect(screen.getByText(/共 2 份/)).toBeInTheDocument();
  });

  it("shows empty state when no recent reports exist", () => {
    mockQuery({ ...reportPage, items: [], total_count: 0 });
    render(<ResearchReportsPanel code="002273" />);

    expect(screen.getByText("最近半年暂无研报数据")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
