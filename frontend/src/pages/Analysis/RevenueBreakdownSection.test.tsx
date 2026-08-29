import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import RevenueBreakdownSection from "./RevenueBreakdownSection";

const mocks = vi.hoisted(() => ({
  useRevenueBreakdown: vi.fn(),
  refetch: vi.fn(),
}));

vi.mock("../../api/queries", () => ({
  useRevenueBreakdown: mocks.useRevenueBreakdown,
}));

const baseData = {
  code: "002273",
  symbol: "sz002273",
  name: "水晶光电",
  source: "sina" as const,
  amount_unit: "CNY_yuan" as const,
  amount_unit_inferred: true,
  by_product: [
    {
      id: "1",
      class_name: "消费电子",
      is_sub_item: false,
      revenue: 2_917_784_378,
      cost: 1_984_031_925,
      gross_profit: 933_752_453,
      revenue_share_pct: 83.8883,
      gross_margin_pct: 32.0021,
    },
    {
      id: "2",
      class_name: "抵销项",
      is_sub_item: false,
      revenue: -20_000,
      cost: -10_000,
      gross_profit: -10_000,
      revenue_share_pct: -0.5,
      gross_margin_pct: null,
    },
  ],
  by_business: [],
  by_region: [{
    id: "3",
    class_name: "外销",
    is_sub_item: false,
    revenue: 2_366_580_385,
    cost: null,
    gross_profit: null,
    revenue_share_pct: 68.0408,
    gross_margin_pct: null,
  }],
};

beforeEach(() => {
  mocks.refetch.mockReset();
  mocks.useRevenueBreakdown.mockReturnValue({
    data: baseData,
    isLoading: false,
    error: null,
    refetch: mocks.refetch,
  });
});

describe("RevenueBreakdownSection", () => {
  it("renders available dimensions and percentage-point values", () => {
    render(<RevenueBreakdownSection code="002273" />);
    const interactive = screen.getByTestId("revenue-breakdown-interactive");

    expect(screen.getByText("营收与毛利构成")).toBeInTheDocument();
    expect(within(interactive).getByText("消费电子")).toBeInTheDocument();
    expect(within(interactive).getByText("83.89%")).toBeInTheDocument();
    expect(within(interactive).getByText("32.00%")).toBeInTheDocument();
    expect(within(interactive).getAllByText("-1.0万")).toHaveLength(2);
    expect(screen.getByText(/上游未提供报告期/)).toBeInTheDocument();
  });

  it("exposes visible row counts for PDF capture", () => {
    render(<RevenueBreakdownSection code="002273" isExportingPdf />);

    expect(
      screen.getAllByTestId("pdf-revenue-dimension").map(
        (section) => section.getAttribute("data-pdf-row-count"),
      ),
    ).toEqual(["2", "1"]);
  });

  it("switches to the selected non-empty dimension", () => {
    render(<RevenueBreakdownSection code="002273" />);

    const interactive = screen.getByTestId("revenue-breakdown-interactive");
    fireEvent.click(screen.getAllByText("地区")[0]);

    expect(within(interactive).getByText("外销")).toBeInTheDocument();
    expect(within(interactive).queryByText("消费电子")).not.toBeInTheDocument();
  });

  it("shows a local empty state", () => {
    mocks.useRevenueBreakdown.mockReturnValue({
      data: { ...baseData, by_product: [], by_business: [], by_region: [] },
      isLoading: false,
      error: null,
      refetch: mocks.refetch,
    });

    render(<RevenueBreakdownSection code="002273" />);

    expect(screen.getByText("暂无营收与毛利构成数据")).toBeInTheDocument();
  });
});
