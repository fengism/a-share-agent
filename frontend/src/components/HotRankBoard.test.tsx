import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { HotRankContent } from "./HotRankBoard";

vi.mock("../hooks/useMediaQuery", () => ({
  useMediaQuery: () => false,
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
  it("keeps complete columns and supports two-axis scrolling in the dashboard rail", () => {
    const { container } = render(
      <MemoryRouter>
        <HotRankContent embedded />
      </MemoryRouter>,
    );

    expect(screen.getByRole("columnheader", { name: "排名" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "代码" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "名称" })).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "关联概念" })).toBeInTheDocument();
    expect(screen.getByText("贵州茅台")).toBeInTheDocument();
    const stockHorizontalScroller = screen.getByRole("region", { name: "热股榜左右滑动区域" });
    expect(stockHorizontalScroller).toHaveClass("hot-rank-horizontal-scroll");
    expect(stockHorizontalScroller.firstElementChild).toHaveStyle({ minWidth: "635px" });

    Object.defineProperty(stockHorizontalScroller, "scrollLeft", { value: 0, writable: true });
    const fireMousePointer = (type: string, clientX: number) => {
      const event = new Event(type, { bubbles: true, cancelable: true });
      Object.defineProperties(event, {
        pointerId: { value: 1 },
        pointerType: { value: "mouse" },
        button: { value: 0 },
        clientX: { value: clientX },
      });
      fireEvent(stockHorizontalScroller, event);
    };
    fireMousePointer("pointerdown", 240);
    fireMousePointer("pointermove", 120);
    expect(stockHorizontalScroller.scrollLeft).toBe(120);
    fireMousePointer("pointerup", 120);

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
});
