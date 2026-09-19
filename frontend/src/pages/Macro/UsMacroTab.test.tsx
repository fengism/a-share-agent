import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({ forceRefresh: vi.fn() }));

vi.mock("../../api/queryHooks/market", () => ({
  useUsMacroData: () => ({
    data: {
      indicators: {
        ppi: { latest: { PPI_MOM: 0.2 }, trend: [] },
      },
      updated_at: "2026-09-14T10:30:00+08:00",
      refreshing: true,
      failed_indicators: { cpi: "temporary" },
    },
    isLoading: false,
    error: null,
  }),
  useForceRefreshUsMacroData: () => ({
    mutate: mocks.forceRefresh,
    isPending: false,
  }),
}));

import UsMacroTab from "./UsMacroTab";

describe("UsMacroTab", () => {
  it("shows background refresh and partial failure state", () => {
    render(<UsMacroTab />);

    expect(screen.getByText(/正在后台刷新美国宏观数据/)).toBeInTheDocument();
    expect(screen.getByText(/部分指标刷新失败：美国 CPI/)).toBeInTheDocument();
    expect(screen.getByText(/快照更新于/)).toBeInTheDocument();
    expect(screen.getByText(/PCE 暂无数据/)).toBeInTheDocument();
    expect(screen.getByText("美国 PCE")).toBeInTheDocument();
    expect(screen.getByText("美国 PPI")).toBeInTheDocument();
    expect(screen.getByText("美国就业细项")).toBeInTheDocument();
    expect(screen.getByText("美国消费者信心")).toBeInTheDocument();
    expect(screen.getByText("美国信用利差")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "刷新美国数据" }));
    expect(mocks.forceRefresh).toHaveBeenCalledTimes(1);
  });
});
