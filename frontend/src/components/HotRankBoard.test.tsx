import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { HotRankContent } from "./HotRankBoard";

/**
 * 看板按**容器宽度**（不是视口宽度）切换宽/窄布局：首页侧栏卡片只有 ~400px 宽，
 * 用视口断点会把 635px 的宽表塞进去，右侧列被 overflow:hidden 永久裁掉。
 * 这里直接桩掉容器宽度来覆盖两种布局。
 */
let containerWidthMock = 0;
vi.mock("../hooks/useContainerWidth", () => ({
  useContainerWidth: () => [() => {}, containerWidthMock] as const,
}));

function queryResult<T>(data: T) {
  return {
    data,
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  };
}

vi.mock("../api/queries", () => ({
  useThsHotRank: () => queryResult([
    {
      rank: 1,
      code: "600519",
      name: "贵州茅台",
      change_pct: 2.35,
      hot_value: 128000,
      concept_tag: "白酒;消费",
      pop_tag: "机构关注",
    },
  ]),
  useThsHotConcept: () => queryResult([
    {
      rank: 1,
      code: "GN001",
      name: "人工智能",
      change_pct: 3.2,
      hot_value: 96000,
      hot_tag: "持续活跃",
      tag: "3家涨停",
    },
  ]),
  useThsHotIndustry: () => queryResult([
    {
      rank: 1,
      code: "HY001",
      name: "半导体",
      change_pct: 1.8,
      hot_value: 88000,
      hot_tag: "资金流入",
      tag: "2家涨停",
    },
  ]),
}));

describe("HotRankContent", () => {
  it("keeps complete columns and supports two-axis scrolling when the container is wide", () => {
    containerWidthMock = 900;
    const { container } = render(
      <MemoryRouter>
        <HotRankContent embedded />
      </MemoryRouter>,
    );

    expect(screen.getByRole("columnheader", { name: "排名" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "代码" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "名称" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "关联概念" })).toBeInTheDocument();

    const codeLink = screen.getByRole("link", { name: "600519" });
    expect(codeLink).toBeInTheDocument();
    expect(codeLink).toHaveAttribute("href", "/stock/600519");
    expect(codeLink).toHaveAttribute("title", "查看贵州茅台（600519）个股详情");

    const nameLink = screen.getByRole("link", { name: "贵州茅台" });
    expect(nameLink).toBeInTheDocument();
    expect(nameLink).toHaveAttribute("href", "/stock/600519");
    expect(nameLink).toHaveAttribute("title", "查看贵州茅台（600519）个股详情");

    const stockHorizontalScroller = screen.getByRole("region", { name: "热股榜左右滑动区域" });
    expect(stockHorizontalScroller).toHaveClass("hot-rank-horizontal-scroll");
    expect(stockHorizontalScroller.firstElementChild).toHaveStyle({ minWidth: "635px" });

    Object.defineProperty(stockHorizontalScroller, "scrollLeft", { value: 0, writable: true });
    const fireMousePointer = (target: Element, type: string, clientX: number) => {
      const event = new Event(type, { bubbles: true, cancelable: true });
      Object.defineProperties(event, {
        pointerId: { value: 1 },
        pointerType: { value: "mouse" },
        button: { value: 0 },
        clientX: { value: clientX },
      });
      fireEvent(target, event);
    };

    // Pointer down on link does NOT initiate drag
    fireMousePointer(codeLink, "pointerdown", 240);
    fireMousePointer(stockHorizontalScroller, "pointermove", 120);
    expect(stockHorizontalScroller.scrollLeft).toBe(0);
    fireMousePointer(stockHorizontalScroller, "pointerup", 120);

    // Pointer down on scroll container / table initiates drag
    fireMousePointer(stockHorizontalScroller, "pointerdown", 240);
    fireMousePointer(stockHorizontalScroller, "pointermove", 120);
    expect(stockHorizontalScroller.scrollLeft).toBe(120);
    fireMousePointer(stockHorizontalScroller, "pointerup", 120);

    expect(container.querySelector(".ant-table")).toHaveClass("ant-table-scroll-horizontal");
    expect(container.querySelector(".ant-table-tbody-virtual-holder")).toHaveStyle({
      maxHeight: "440px",
    });
    expect(container.querySelector(".ant-table-tbody-virtual-scrollbar-horizontal")).toBeInTheDocument();
    expect(container.querySelector(".ant-table-row")).toHaveStyle({ width: "635px" });

    fireEvent.click(screen.getByText("概念榜"));

    const conceptTable = screen.getAllByRole("table")[0];
    expect(within(conceptTable).getByRole("columnheader", { name: "概念名称" })).toBeInTheDocument();
    expect(within(conceptTable).getByRole("columnheader", { name: "上榜标签" })).toBeInTheDocument();
    expect(container.querySelector(".ant-table")).toHaveClass("ant-table-scroll-horizontal");
    expect(container.querySelector(".ant-table-body")).toHaveStyle({
      maxHeight: "440px",
      overflowX: "auto",
    });
    expect(conceptTable).toHaveStyle({ width: "655px" });
  });

  it("switches to the compact layout when the container is too narrow for the wide table", () => {
    // 首页侧栏卡片 ~400px：即使视口 1600px 也必须用紧凑布局，否则右列被裁掉
    containerWidthMock = 406;
    render(
      <MemoryRouter>
        <HotRankContent embedded />
      </MemoryRouter>,
    );

    // 紧凑布局：合并"代码+名称"为一列，只保留涨跌幅与热度
    expect(screen.getByRole("columnheader", { name: "股票" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "涨跌幅" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "热度" })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "关联概念" })).not.toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "排名" })).not.toBeInTheDocument();

    // 横向滚动区宽度必须跟着切到 316px，否则仍会把表格撑出容器
    const scroller = screen.getByRole("region", { name: "热股榜左右滑动区域" });
    expect(scroller.firstElementChild).toHaveStyle({ minWidth: "316px" });
  });

  it("renders clickable stock links in the compact layout", () => {
    containerWidthMock = 406;
    render(
      <MemoryRouter>
        <HotRankContent embedded />
      </MemoryRouter>,
    );

    const stockLink = screen.getByRole("link", { name: /贵州茅台.*600519/ });
    expect(stockLink).toBeInTheDocument();
    expect(stockLink).toHaveAttribute("href", "/stock/600519");
    expect(stockLink).toHaveAttribute("title", "查看贵州茅台（600519）个股详情");
  });
});

