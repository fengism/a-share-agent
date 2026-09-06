import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import CommoditiesTab from "./CommoditiesTab";

vi.mock("../../api/queries", () => ({
  useCommoditySpotPrices: () => ({
    data: {
      query: "all",
      total_count: 2,
      items: [
        {
          symbol: "碳酸锂",
          name: "碳酸锂连续",
          contract: "LC0",
          category: "新能源金属",
          unit: "元/吨",
          latest_price: 154700,
          change: -5260,
          change_pct: -3.29,
          high: 157820,
          low: 153200,
          open: 157000,
          prev_settle: 159960,
          volume: 397016,
          open_interest: 129601,
          date: "2026-09-02",
          description: "锂电池核心原材料",
          related_chains: ["锂电池", "新能源汽车"],
        },
        {
          symbol: "沪铜",
          name: "电解铜连续",
          contract: "CU0",
          category: "有色金属",
          unit: "元/吨",
          latest_price: 107850,
          change: -1670,
          change_pct: -1.52,
          high: 108750,
          low: 107460,
          open: 108500,
          prev_settle: 109520,
          volume: 207728,
          open_interest: 112405,
          date: "2026-09-02",
          description: "电网与电子核心导电材料",
          related_chains: ["电网设备", "PCB"],
        },
      ],
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

describe("CommoditiesTab", () => {
  it("renders commodity items and categories", () => {
    render(<CommoditiesTab />);
    expect(screen.getByText("碳酸锂连续")).toBeInTheDocument();
    expect(screen.getByText("电解铜连续")).toBeInTheDocument();
    expect(screen.getAllByText("新能源金属").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("有色金属").length).toBeGreaterThanOrEqual(1);
  });
});
