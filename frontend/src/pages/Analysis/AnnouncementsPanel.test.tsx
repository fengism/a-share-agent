import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { StockBulletinPage } from "../../types/stock";
import AnnouncementsPanel from "./AnnouncementsPanel";

const useStockBulletinsMock = vi.fn();

vi.mock("../../api/queries", () => ({
  useStockBulletins: (...args: unknown[]) => useStockBulletinsMock(...args),
}));

function mockQuery(data: StockBulletinPage | undefined, isLoading = false, error: unknown = null) {
  useStockBulletinsMock.mockReturnValue({
    data,
    isLoading,
    error,
    refetch: vi.fn(),
  });
}

const bulletinPage: StockBulletinPage = {
  code: "002273",
  name: "水晶光电",
  page: 1,
  page_size: 10,
  total_pages: 12,
  source: "sina_stock_bulletins",
  items: [
    {
      id: "12551947",
      title: "水晶光电：2026年第二次临时股东会法律意见书",
      date: "2026-08-27",
      type: "法律意见书",
      type2: "",
      url: "http://cj.sina.com.cn/announcement/detail?id=12551947",
      pdf_url: "http://file.finance.sina.com.cn/12551947.PDF",
      origin: "巨潮资讯网",
      source: "sina_stock_bulletins",
      source_api: "CB_AllService.getBulletinList",
    },
    {
      id: "12551944",
      title: "水晶光电：关于完成补选非独立董事的公告",
      date: "2026-08-27",
      type: "临时公告",
      type2: "高管变动",
      url: "",
      pdf_url: "",
      origin: "巨潮资讯网",
      source: "sina_stock_bulletins",
      source_api: "CB_AllService.getBulletinList",
    },
  ],
};

describe("AnnouncementsPanel", () => {
  it("renders bulletin list with links and pagination", () => {
    mockQuery(bulletinPage);
    const { container } = render(<AnnouncementsPanel code="002273" />);

    expect(useStockBulletinsMock).toHaveBeenCalledWith("002273", 1, 10);
    expect(screen.getByText("水晶光电：2026年第二次临时股东会法律意见书")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "水晶光电：2026年第二次临时股东会法律意见书" }))
      .toHaveAttribute("href", bulletinPage.items[0].url);
    expect(screen.getByRole("link", { name: "PDF" })).toBeInTheDocument();
    expect(screen.getByText("临时公告")).toBeInTheDocument();
    expect(screen.getByText("高管变动")).toBeInTheDocument();
    expect(screen.getAllByText(/巨潮资讯网/)).toHaveLength(2);
    const list = container.querySelector("ul.analysis-detail-list");
    expect(list).not.toBeNull();
    expect(within(list as HTMLElement).getAllByRole("listitem")).toHaveLength(2);
    expect(container.querySelector(".ant-pagination")).not.toBeNull();
  });

  it("shows empty state without pagination when no bulletins exist", () => {
    mockQuery({ ...bulletinPage, items: [], total_pages: 0 });
    const { container } = render(<AnnouncementsPanel code="002273" />);

    expect(screen.getByText("暂无公告数据")).toBeInTheDocument();
    expect(container.querySelector(".ant-pagination")).toBeNull();
  });

  it("labels the disclosure source from the response", () => {
    mockQuery({ ...bulletinPage, source: "cninfo_stock_bulletins" });
    render(<AnnouncementsPanel code="002273" />);

    expect(screen.getByText("来源：巨潮资讯")).toBeInTheDocument();
    expect(screen.getByText(/巨潮资讯公告列表/)).toBeInTheDocument();
  });
});
