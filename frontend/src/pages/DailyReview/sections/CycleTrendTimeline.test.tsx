import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import CycleTrendTimeline from "./CycleTrendTimeline";

const trend = {
  note: "近 10 个交易日情绪阶段演进",
  points: [
    {
      date: "2026-10-27",
      stage: "冰点",
      stage_transition: "降级",
      limit_up_count: 18,
      break_rate: 0.32,
      index_change_pct: -1.2,
      next_index_change_pct: 0.4,
    },
    {
      date: "2026-10-28",
      stage: "修复回暖",
      stage_transition: "升级",
      limit_up_count: 36,
      break_rate: 0.18,
      index_change_pct: 0.85,
    },
  ],
  stage_stats: [
    { stage: "修复回暖", occurrences: 2, next_day_up_ratio: 0.5, avg_next_day_index_change_pct: -0.42 },
  ],
};

describe("CycleTrendTimeline", () => {
  it("renders points in chronological order with stage and metrics", () => {
    render(<CycleTrendTimeline trend={trend} />);

    expect(screen.getByText(/近 10 个交易日情绪阶段演进/)).toBeInTheDocument();

    const nodes = within(screen.getByRole("list", { name: "情绪周期时间轴" })).getAllByRole("listitem");
    expect(nodes).toHaveLength(2);
    expect(within(nodes[0]).getByText("冰点")).toBeInTheDocument();
    expect(within(nodes[0]).getByText(/32\.0%/)).toBeInTheDocument();
    expect(within(nodes[1]).getByText("修复回暖")).toBeInTheDocument();
    expect(within(nodes[1]).getByText(/\+0\.85%/)).toBeInTheDocument();
  });

  it("shows the stage statistics summary", () => {
    render(<CycleTrendTimeline trend={trend} />);

    expect(screen.getByText(/出现 2 次/)).toBeInTheDocument();
    expect(screen.getByText(/平均次日 -0.42%/)).toBeInTheDocument();
  });

  it("renders nothing when there are no points", () => {
    const { container } = render(<CycleTrendTimeline trend={{ points: [] }} />);
    expect(container).toBeEmptyDOMElement();
  });
});
