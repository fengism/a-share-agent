import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { DragonTigerContent } from "./DragonTigerContent";

const mocks = vi.hoisted(() => ({
  detailQuery: vi.fn(),
}));

vi.mock("../../api/queries", () => ({
  useDragonTigerList: () => ({
    data: [
      {
        code: "600000",
        name: "浦发银行",
        trade_date: "2026-09-04",
        close: 10,
        change_pct: 2.1,
        turnover_pct: 3.2,
        net_amount: 100,
        buy_amount: 300,
        sell_amount: 200,
        deal_amount: 500,
        total_amount: 1_000,
        net_amount_rate: 10,
        deal_amount_rate: 20,
        reason: "日涨幅偏离值达7%",
        explain: "",
        d1_chg: null,
        d2_chg: null,
        d5_chg: null,
      },
    ],
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useDragonTigerDetail: (code: string, reportDate: string) => {
    mocks.detailQuery(code, reportDate);
    return {
      data: [],
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    };
  },
}));

vi.mock("../../hooks/useMediaQuery", () => ({
  useMediaQuery: () => false,
}));

describe("DragonTigerContent", () => {
  it("shows the resolved trading date and loads row details with that date", async () => {
    mocks.detailQuery.mockClear();
    render(
      <MemoryRouter>
        <DragonTigerContent />
      </MemoryRouter>,
    );

    expect(screen.getByText("实际数据日期：2026-09-04")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "席位" }));

    await waitFor(() => {
      expect(mocks.detailQuery).toHaveBeenCalledWith("600000", "2026-09-04");
    });
  });

  it("supports exporting dragon tiger list to CSV", () => {
    window.URL.createObjectURL = vi.fn(() => "blob:mock-url");
    window.URL.revokeObjectURL = vi.fn();
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    render(
      <MemoryRouter>
        <DragonTigerContent />
      </MemoryRouter>,
    );

    const exportBtn = screen.getByRole("button", { name: "导出龙虎榜 CSV" });
    expect(exportBtn).toBeInTheDocument();
    fireEvent.click(exportBtn);

    expect(window.URL.createObjectURL).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
    clickSpy.mockRestore();
  });
});
