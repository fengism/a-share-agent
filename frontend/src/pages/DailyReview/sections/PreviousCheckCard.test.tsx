import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import PreviousCheckCard from "./PreviousCheckCard";

const check = {
  review_date: "2026-10-28",
  verified_date: "2026-10-29",
  previous_stage: "分歧",
  hit_count: 1,
  checked_count: 2,
  limit_up_count: 42,
  previous_limit_up_count: 55,
  limit_up_delta: -13,
  watchlist: [
    { name: "甲", code: "600001", change_pct: 10, hit: true, limit_up: true },
    { name: "乙", code: "600002", change_pct: -3.2, hit: false },
    { name: "丙", code: "600003", missing: true },
  ],
  indices: [{ name: "上证指数", previous_change_pct: 0.8, change_pct: -0.42 }],
  note: "乙冲高回落，说明分歧未结束。",
};

describe("PreviousCheckCard", () => {
  it("renders the hit rate ring and the item-by-item comparison", () => {
    render(<PreviousCheckCard check={check as never} accuracy={0.5} />);

    expect(screen.getByText("50%")).toBeInTheDocument();
    expect(screen.getByText(/2026-10-28 复盘 → 2026-10-29/)).toBeInTheDocument();
    expect(screen.getByText(/昨日周期：分歧/)).toBeInTheDocument();
    expect(screen.getByText(/涨停家数 55 → 42/)).toBeInTheDocument();

    const table = screen.getByRole("table", { name: "观察锚点逐项对照" });
    const rows = within(table).getAllByRole("row");
    // 表头 + 3 条观察锚点
    expect(rows).toHaveLength(4);
    expect(within(table).getByText("命中")).toBeInTheDocument();
    expect(within(table).getByText("未命中")).toBeInTheDocument();
    expect(within(table).getByText("无数据")).toBeInTheDocument();
    expect(within(table).getByText("+10.00%")).toBeInTheDocument();
    expect(within(table).getByText("-3.20%")).toBeInTheDocument();
    expect(screen.getByText(/上证指数：\+0.80% → -0.42%/)).toBeInTheDocument();
    expect(screen.getByText(/乙冲高回落/)).toBeInTheDocument();
  });

  it("falls back to an explicit hint when nothing could be verified", () => {
    render(
      <PreviousCheckCard
        check={{ review_date: "2026-10-28", verified_date: "2026-10-29", watchlist: [], hit_count: 0, checked_count: 0 } as never}
        accuracy={null}
      />,
    );

    expect(screen.getByText("暂无可核验行情")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
