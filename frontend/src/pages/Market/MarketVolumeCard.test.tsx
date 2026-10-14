import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MarketVolumeCard from "./MarketVolumeCard";

const mockUseMarketVolume = vi.fn();

vi.mock("../../api/queries", () => ({
  useMarketVolume: () => mockUseMarketVolume(),
}));

vi.mock("echarts-for-react/lib/core", () => ({
  default: ({ option }: { option: Record<string, unknown> }) => (
    <div data-testid="echarts-volume-mock" data-option={JSON.stringify(option)} />
  ),
}));
vi.mock("../../charts/echarts-setup", () => ({ default: {} }));

describe("MarketVolumeCard", () => {
  beforeEach(() => {
    mockUseMarketVolume.mockReset();
  });

  it("renders empty state when data is empty", () => {
    mockUseMarketVolume.mockReturnValue({
      data: { items: [] },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<MarketVolumeCard />);
    expect(screen.getByText("A股全市场成交额走势")).toBeInTheDocument();
    expect(screen.getByText("暂无全市场成交额数据")).toBeInTheDocument();
  });

  it("renders statistics and chart when volume series is available", () => {
    const mockItems = Array.from({ length: 65 }, (_, i) => {
      const day = String(i + 1).padStart(2, "0");
      return {
        date: `2026-08-${day}`,
        amount: (10000 + i * 100) * 1e8, // 10,000 ~ 16,400 亿元
        volume: 50000000,
      };
    });

    mockUseMarketVolume.mockReturnValue({
      data: { items: mockItems },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<MarketVolumeCard />);

    expect(screen.getByText("A股全市场成交额走势")).toBeInTheDocument();
    expect(screen.getByText("最新全市场成交")).toBeInTheDocument();
    expect(screen.getByText("20日均量 (MA20)")).toBeInTheDocument();
    expect(screen.getByText("区间最高 (天量)")).toBeInTheDocument();
    expect(screen.getByText("区间最低 (地量)")).toBeInTheDocument();

    const chartMock = screen.getByTestId("echarts-volume-mock");
    expect(chartMock).toBeInTheDocument();
    const option = JSON.parse(chartMock.getAttribute("data-option") || "{}");
    // Default range is 60 items
    expect(option.xAxis.data).toHaveLength(60);
    expect(option.series[0].name).toBe("成交额");
    expect(option.series[1].name).toBe("MA5");
    expect(option.series[2].name).toBe("MA20");
  });

  it("updates display items count when switching range", () => {
    const mockItems = Array.from({ length: 70 }, (_, i) => ({
      date: `2026-08-${String(i + 1).padStart(2, "0")}`,
      amount: 12000 * 1e8,
      volume: 40000000,
    }));

    mockUseMarketVolume.mockReturnValue({
      data: { items: mockItems },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<MarketVolumeCard />);

    // Switch to 近30日
    const btn30 = screen.getByText("近30日");
    fireEvent.click(btn30);

    const chartMock = screen.getByTestId("echarts-volume-mock");
    const option30 = JSON.parse(chartMock.getAttribute("data-option") || "{}");
    expect(option30.xAxis.data).toHaveLength(30);

    // Switch to 近1年 (all 70 items)
    const btnAll = screen.getByText("近1年");
    fireEvent.click(btnAll);

    const optionAll = JSON.parse(chartMock.getAttribute("data-option") || "{}");
    expect(optionAll.xAxis.data).toHaveLength(70);
  });
});
