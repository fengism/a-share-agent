import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import Concept from "./index";

const hooks = vi.hoisted(() => ({
  list: vi.fn(),
  constituents: vi.fn(),
  index: vi.fn(),
}));

vi.mock("../../api/queryHooks/concept", () => ({
  useConceptList: () => hooks.list(),
  useConceptConstituents: () => hooks.constituents(),
  useConceptIndex: () => hooks.index(),
}));

vi.mock("../../charts/KlineChart", () => ({
  default: ({ data }: { data: Array<{ date: string; close: number }> }) => (
    <div data-testid="kline">K线 {data.length} 根，收盘 {data.at(-1)?.close}</div>
  ),
}));

const CONCEPTS = [
  { name: "融资融券", stock_count: 3861 },
  { name: "固态电池", stock_count: 297 },
  { name: "宁德时代概念", stock_count: 199 },
  { name: "钠离子电池", stock_count: 92 },
];

function setup() {
  hooks.list.mockReturnValue({ data: { items: CONCEPTS }, isLoading: false, isFetching: false, error: null });
  hooks.constituents.mockReturnValue({
    data: {
      concept: "融资融券",
      total: 3861,
      quote_source: "tdxhub",
      related_concepts: [{ name: "固态电池", overlap: 12, ratio: 0.003 }],
      items: [{ code: "000002", name: "万科A", price: 4.26, change_pct: 1, amount: 1 }],
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  });
  hooks.index.mockReturnValue({
    data: {
      concept: "融资融券",
      constituent_total: 3861,
      constituent_used: 800,
      truncated: true,
      items: [{ date: "2026-09-30", open: 1, high: 1, low: 1, close: 972.37, change_pct: 0.5, amount: 1, up_count: 433, down_count: 333, limit_up_count: 1, limit_down_count: 0, sample_count: 800 }],
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  });
  return render(
    <MemoryRouter initialEntries={["/concept"]}>
      <Concept />
    </MemoryRouter>,
  );
}

describe("Concept page", () => {
  it("falls back to the largest concept when the URL carries none", async () => {
    setup();
    await waitFor(() => expect(screen.getByText("融资融券 · 3861 只")).toBeInTheDocument());
  });

  it("renders the synthesized index and the constituent table", async () => {
    setup();
    expect(await screen.findByTestId("kline")).toHaveTextContent("收盘 972.37");
    expect(screen.getByLabelText("合成指数点位")).toHaveTextContent("972.37");
    expect(screen.getByText("样本 800/800")).toBeInTheDocument();
    expect(screen.getByText("万科A")).toBeInTheDocument();
  });

  /**
   * 回归：AutoComplete 的候选项必须跟着输入过滤。
   * 之前把搜索词只接在另一个输入框上，导致在这里输入"固态电池"，
   * 下拉仍显示按成分股数排序的前 10 个（第一条是"融资融券 3861 只"）。
   */
  it("filters the concept options by what the user typed", async () => {
    const { container } = setup();
    const combo = container.querySelector(".ant-select input") as HTMLInputElement;
    expect(combo).toBeTruthy();

    fireEvent.change(combo, { target: { value: "固态电池" } });

    // 输入过滤是纯前端计算（useConceptSearch），不依赖下拉是否在 jsdom 里展开
    await waitFor(() => {
      expect(screen.getByText("共 4 个概念 · 匹配 1")).toBeInTheDocument();
    });
  });

  it("shows the whole concept catalogue size when nothing is typed", async () => {
    setup();
    await waitFor(() => expect(screen.getByText("共 4 个概念")).toBeInTheDocument());
  });
});