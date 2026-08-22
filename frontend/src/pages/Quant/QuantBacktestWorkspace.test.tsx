import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import QuantBacktestWorkspace from "./QuantBacktestWorkspace";
import type { QuantRunController } from "./useQuantRunController";

const createdRun = {
  id: "new-run",
  name: "新回测",
  status: "pending" as const,
  attempts: 0,
  created_at: 1,
  updated_at: 1,
  completed_at: null,
  request: {
    name: "新回测",
    universe: { source: "custom" as const, codes: ["600519"] },
    strategy: { type: "ma_cross" as const, version: "1.0.0", parameters: {} },
    start_date: "2025-01-01",
    end_date: "2026-01-01",
    benchmark: "000300",
  },
};

vi.mock("./BacktestForm", () => ({
  default: ({ onCreated }: { onCreated: (run: typeof createdRun) => void }) => (
    <button type="button" onClick={() => onCreated(createdRun)}>创建测试回测</button>
  ),
}));
vi.mock("./BacktestTaskWorkspace", () => ({ default: () => <div>独立任务视图</div> }));
vi.mock("./BacktestResultSection", () => ({ default: () => <div>独立结果视图</div> }));

function LocationProbe() {
  return <div data-testid="location-search">{useLocation().search}</div>;
}

describe("QuantBacktestWorkspace", () => {
  it("moves a newly created run to the task view and keeps each view independent", async () => {
    const selectRun = vi.fn();
    const controller = {
      runs: [createdRun],
      selectedRun: undefined,
      selectedRunId: "",
      selectRun,
    } as unknown as QuantRunController;
    render(
      <MemoryRouter>
        <QuantBacktestWorkspace initialCodes={["600519"]} runController={controller} />
        <LocationProbe />
      </MemoryRouter>,
    );

    expect(screen.getByRole("region", { name: "量化回测配置" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /任务记录.*1/ })).toBeInTheDocument();
    expect(screen.queryByText("独立任务视图")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "创建测试回测" }));

    expect(await screen.findByText("独立任务视图")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("location-search")).toHaveTextContent("panel=runs"));
    expect(screen.getByTestId("location-search")).toHaveTextContent("run=new-run");

    fireEvent.click(screen.getByRole("tab", { name: /结果分析/ }));
    expect(screen.getByText("独立结果视图")).toBeInTheDocument();
  });
});
