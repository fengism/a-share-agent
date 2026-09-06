import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import GrowthTab from "./GrowthTab";

const mocks = vi.hoisted(() => ({
  refetch: vi.fn(),
}));

vi.mock("../../api/queries", () => ({
  useMacroAllData: () => ({
    data: {
      growth: {
        industrial_production: {
          latest: {
            TIME: "2026-07",
            VALUE_ADDED_YOY: 5.7,
            VALUE_ADDED_ACCUMULATE_YOY: 6.3,
          },
          trend: [],
          source: "nbs",
        },
        retail_sales: {
          latest: {
            TIME: "2026-07",
            RETAIL_VALUE: 38780,
            RETAIL_YOY: 3.7,
            RETAIL_ACCUMULATE: 284413,
            RETAIL_ACCUMULATE_YOY: 4.8,
          },
          trend: [],
          source: "nbs",
        },
        fixed_asset_investment: {
          latest: {
            TIME: "2026-07",
            INVESTMENT_ACCUMULATE_YOY: 3.6,
          },
          trend: [],
          source: "nbs",
        },
        real_estate: {
          latest: {
            TIME: "2026-07",
            DEVELOPMENT_INVESTMENT: 53580,
            DEVELOPMENT_INVESTMENT_YOY: -8.1,
            SALES_AREA: 51560,
            SALES_AREA_YOY: -4.0,
            SALES_VALUE: 49566,
            SALES_VALUE_YOY: -6.5,
          },
          trend: [],
          source: "nbs",
        },
        employment: {
          latest: {
            TIME: "2026-07",
            URBAN_SURVEYED_UNEMPLOYMENT: 5.2,
            CITY31_SURVEYED_UNEMPLOYMENT: 5.2,
          },
          trend: [],
          source: "nbs",
        },
      },
    },
    isLoading: false,
    error: null,
    refetch: mocks.refetch,
  }),
}));

describe("GrowthTab", () => {
  it("renders the five NBS growth and employment indicators", () => {
    render(<GrowthTab />);

    expect(screen.getByText("规模以上工业增加值")).toBeInTheDocument();
    expect(screen.getByText("社会消费品零售总额")).toBeInTheDocument();
    expect(screen.getByText("固定资产投资")).toBeInTheDocument();
    expect(screen.getByText("房地产开发与销售")).toBeInTheDocument();
    expect(screen.getByText("城镇调查失业率")).toBeInTheDocument();
    expect(screen.getAllByText("国家统计局")).toHaveLength(5);
    expect(screen.getAllByText("万亿元")).toHaveLength(4);
    expect(screen.getByText("亿平方米")).toBeInTheDocument();
    const values = Array.from(document.querySelectorAll(".ant-statistic-content"), (node) => node.textContent);
    expect(values).toContain("3.88万亿元");
    expect(values).toContain("5.16亿平方米");
  });
});
