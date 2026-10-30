import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import StockNewsPanel from "./StockNewsPanel";

const mockNewsQuery = vi.fn();
vi.mock("../../api/queries", () => ({
  useCategorizedStockNews: (...args: unknown[]) => mockNewsQuery(...args),
}));

describe("StockNewsPanel", () => {
  it("renders news cards for CLS and Eastmoney news", () => {
    mockNewsQuery.mockReturnValue({
      data: {
        cls_news: [
          { title: "贵州茅台发布第三季度业绩公告", source: "财联社", publish_time: "2026-10-28 17:30", url: "https://example.com/news1" },
        ],
        eastmoney_news: [
          { title: "白酒板块集体反弹 茅台成交额超50亿", source: "东方财富", publish_time: "2026-10-28 15:00", url: "" },
        ],
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<StockNewsPanel code="600519" />);

    expect(screen.getByText("财联社快讯（1）")).toBeInTheDocument();
    expect(screen.getByText("东方财富资讯（1）")).toBeInTheDocument();
    expect(screen.getByText("贵州茅台发布第三季度业绩公告")).toBeInTheDocument();
    expect(screen.getByText("白酒板块集体反弹 茅台成交额超50亿")).toBeInTheDocument();
  });

  it("handles empty news gracefully", () => {
    mockNewsQuery.mockReturnValue({
      data: { cls_news: [], eastmoney_news: [] },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<StockNewsPanel code="600519" />);
    expect(screen.getByText("暂无相关新闻")).toBeInTheDocument();
  });

  it("filters news by quick tag or keyword input", () => {
    mockNewsQuery.mockReturnValue({
      data: {
        cls_news: [
          { title: "贵州茅台发布前三季度业绩大幅增长公告", source: "财联社", publish_time: "2026-10-28 17:30", url: "https://example.com/news1" },
          { title: "高管增持计划实施完成", source: "财联社", publish_time: "2026-10-28 18:00", url: "" },
        ],
        eastmoney_news: [
          { title: "白酒板块集体反弹", source: "东方财富", publish_time: "2026-10-28 15:00", url: "" },
        ],
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<StockNewsPanel code="600519" />);

    // Click quick tag "业绩"
    const yejiTag = screen.getByText("业绩");
    fireEvent.click(yejiTag);

    expect(screen.getByText("财联社快讯（1/2）")).toBeInTheDocument();
    expect(screen.getByText("东方财富资讯（0/1）")).toBeInTheDocument();
    expect(screen.getByText(/未找到包含/)).toBeInTheDocument();

    // Clear by clicking "全部"
    const allTag = screen.getByText("全部");
    fireEvent.click(allTag);
    expect(screen.getByText("财联社快讯（2）")).toBeInTheDocument();
  });
});
