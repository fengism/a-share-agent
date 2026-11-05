import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import SectorRRGChart from "./SectorRRGChart";
import type { IndustryRankItem } from "../../types/stock";

const sampleSectors: IndustryRankItem[] = [
  {
    rank: 1,
    name: "半导体",
    code: "881121",
    change_pct: 3.5,
    amount: 50_000_000_000,
    net_inflow: 2_500_000_000,
    buy_amount: 26_000_000_000,
    sell_amount: -23_500_000_000,
    turnover_rate: 2.1,
    market_cap: 1_200_000_000_000,
    up_count: 35,
    down_count: 5,
    leader: "中芯国际",
    leader_change: 6.2,
    avg_change: 3.2,
  },
  {
    rank: 2,
    name: "贵金属",
    code: "881169",
    change_pct: -1.2,
    amount: 15_000_000_000,
    net_inflow: 800_000_000,
    buy_amount: 7_900_000_000,
    sell_amount: -7_100_000_000,
    turnover_rate: 1.5,
    market_cap: 800_000_000_000,
    up_count: 4,
    down_count: 8,
    leader: "山东黄金",
    leader_change: 1.5,
    avg_change: -1.0,
  },
  {
    rank: 3,
    name: "房地产",
    code: "881153",
    change_pct: -2.8,
    amount: 20_000_000_000,
    net_inflow: -1_500_000_000,
    buy_amount: 9_200_000_000,
    sell_amount: -10_700_000_000,
    turnover_rate: 1.0,
    market_cap: 900_000_000_000,
    up_count: 5,
    down_count: 50,
    leader: "万科A",
    leader_change: -1.2,
    avg_change: -2.5,
  },
  {
    rank: 4,
    name: "电力",
    code: "881145",
    change_pct: 1.1,
    amount: 18_000_000_000,
    net_inflow: -600_000_000,
    buy_amount: 8_700_000_000,
    sell_amount: -9_300_000_000,
    turnover_rate: 1.2,
    market_cap: 1_000_000_000_000,
    up_count: 22,
    down_count: 15,
    leader: "长江电力",
    leader_change: 1.8,
    avg_change: 0.9,
  },
];

describe("SectorRRGChart", () => {
  it("renders quadrant labels and sectors properly", () => {
    render(<SectorRRGChart sectors={sampleSectors} />);

    expect(screen.getByText(/行业板块轮动四象限全景/)).toBeInTheDocument();
    expect(screen.getAllByText(/领先加速/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/拐点改善/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/冲高回落/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/筑底滞后/).length).toBeGreaterThan(0);
    expect(screen.getByText("半导体")).toBeInTheDocument();
    expect(screen.getByText("贵金属")).toBeInTheDocument();
  });

  it("triggers onSelectSector when a sector bubble is clicked", () => {
    const handleSelect = vi.fn();
    render(<SectorRRGChart sectors={sampleSectors} onSelectSector={handleSelect} />);

    const bubbleText = screen.getByText("半导体");
    fireEvent.click(bubbleText);

    expect(handleSelect).toHaveBeenCalledWith({
      code: "881121",
      name: "半导体",
    });
  });

  it("renders history trail lines when provided and toggles trails visibility", () => {
    const mockTrails = {
      "881121": [
        { x: 1.0, y: 1.0, date: "2026-10-25" },
        { x: 2.2, y: 3.0, date: "2026-10-26" },
        { x: 3.5, y: 5.0, date: "2026-10-27" },
      ],
    };

    const { container } = render(
      <SectorRRGChart sectors={sampleSectors} historyTrails={mockTrails} />,
    );

    expect(screen.getByText(/轨迹连线已开启/)).toBeInTheDocument();
    expect(container.querySelector(".rrg-trail-path--leading")).toBeInTheDocument();

    const switchBtn = screen.getByText(/轨迹连线已开启/);
    fireEvent.click(switchBtn);

    expect(screen.getByText(/显示历史轨迹/)).toBeInTheDocument();
    expect(container.querySelector(".rrg-trail-path--leading")).not.toBeInTheDocument();
  });
});
