import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PriceTab from "./PriceTab";

vi.mock("../../api/queries", () => ({
  useMacroAllData: () => ({
    data: {
      prices: {
        cpi: {
          latest: {
            TIME: "2026-08",
            NATIONAL_SAME: 0.6,
            NATIONAL_SEQUENTIAL: 0.1,
            NATIONAL_ACCUMULATE: 0.4,
          },
          trend: [],
          source: "nbs",
        },
        ppi: {
          latest: {
            TIME: "2026-08",
            BASE_SAME: -1.2,
            BASE_ACCUMULATE: -1.5,
          },
          trend: [],
          source: "nbs",
        },
      },
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

describe("PriceTab", () => {
  it("renders inflation indicators, scissors gap, and chart cards", () => {
    render(<PriceTab />);

    expect(screen.getByText("💡 CPI - PPI 工业与消费物价剪刀差研判")).toBeInTheDocument();
    expect(screen.getByText("剪刀差为正（中下游毛利偏好）")).toBeInTheDocument();
    expect(screen.getByText("CPI 居民消费价格 (同比)")).toBeInTheDocument();
    expect(screen.getByText("PPI 工业出厂价格 (同比)")).toBeInTheDocument();
    expect(screen.getByText("CPI - PPI 利润剪刀差")).toBeInTheDocument();
    expect(screen.getByText("CPI 居民消费价格指数")).toBeInTheDocument();
    expect(screen.getByText("PPI 工业生产者出厂价格指数")).toBeInTheDocument();
  });
});
