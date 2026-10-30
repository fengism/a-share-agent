import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import ConceptComparePanel from "./ConceptComparePanel";

const hooks = vi.hoisted(() => ({
  list: vi.fn(),
  series: vi.fn(),
}));

vi.mock("../../api/queryHooks/concept", () => ({
  useConceptList: () => hooks.list(),
  useConceptIndexSeries: (...args: unknown[]) => hooks.series(...args),
}));

// echarts 在 jsdom 里没有 canvas，直接渲染会告警/超时，测试里用占位组件
vi.mock("echarts-for-react/lib/core", () => ({
  default: ({ option }: { option: { series: Array<{ name: string }> } }) => (
    <div data-testid="compare-chart">
      系列：{option.series.map((item) => item.name).join("|")}
    </div>
  ),
}));

const POINTS_A = [
  { date: "2026-09-26", open: 1000, high: 1010, low: 990, close: 1000, change_pct: 0, up_count: 1, down_count: 1, limit_up_count: 0, limit_down_count: 0, sample_count: 2, amount: 1 },
  { date: "2026-09-27", open: 1000, high: 1030, low: 995, close: 1050, change_pct: 5, up_count: 2, down_count: 0, limit_up_count: 0, limit_down_count: 0, sample_count: 2, amount: 1 },
];

const POINTS_B = [
  { date: "2026-09-26", open: 2000, high: 2010, low: 1990, close: 2000, change_pct: 0, up_count: 1, down_count: 1, limit_up_count: 0, limit_down_count: 0, sample_count: 2, amount: 1 },
  { date: "2026-09-27", open: 2000, high: 2005, low: 1950, close: 1940, change_pct: -3, up_count: 0, down_count: 2, limit_up_count: 0, limit_down_count: 0, sample_count: 2, amount: 1 },
];

function renderPanel(overrides: Partial<Parameters<typeof ConceptComparePanel>[0]> = {}) {
  return render(
    <MemoryRouter>
      <ConceptComparePanel
        mainConcept="机器人概念"
        compareConcepts={["固态电池"]}
        days={365}
        onAdd={vi.fn()}
        onRemove={vi.fn()}
        onSelectMain={vi.fn()}
        {...overrides}
      />
    </MemoryRouter>,
  );
}

describe("ConceptComparePanel", () => {
  it("overlays every selected concept as a normalized series", () => {
    hooks.list.mockReturnValue({ data: { items: [{ name: "钠离子电池", stock_count: 9 }] } });
    hooks.series.mockReturnValue([
      { data: { items: POINTS_A }, isLoading: false },
      { data: { items: POINTS_B }, isLoading: false },
    ]);

    renderPanel();

    expect(screen.getByTestId("compare-chart")).toHaveTextContent("机器人概念|固态电池");
    // 区间涨跌幅图例：主概念 +5%、对比概念 -3%
    expect(screen.getByText("+5.00%")).toBeInTheDocument();
    expect(screen.getByText("-3.00%")).toBeInTheDocument();
  });

  it("removes a compare concept from the legend", () => {
    hooks.list.mockReturnValue({ data: { items: [] } });
    hooks.series.mockReturnValue([
      { data: { items: POINTS_A }, isLoading: false },
      { data: { items: POINTS_B }, isLoading: false },
    ]);
    const onRemove = vi.fn();

    renderPanel({ onRemove });
    fireEvent.click(screen.getByLabelText("移出对比-固态电池").closest(".ant-tag") as HTMLElement);
    expect(onRemove).toHaveBeenCalledWith("固态电池");
  });

  it("shows the empty state when no series has loaded", () => {
    hooks.list.mockReturnValue({ data: { items: [] } });
    hooks.series.mockReturnValue([
      { data: undefined, isLoading: false },
      { data: undefined, isLoading: false },
    ]);

    renderPanel({ compareConcepts: [] });
    expect(screen.getByText(/暂无对比数据/)).toBeInTheDocument();
  });
});
