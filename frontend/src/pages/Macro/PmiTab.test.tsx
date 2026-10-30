import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PmiTab from "./PmiTab";

vi.mock("../../api/queries", () => ({
  useMacroAllData: () => ({
    data: {
      sentiment: {
        pmi: {
          latest: {
            TIME: "2026-08",
            MAKE_INDEX: 50.8,
            NMAKE_INDEX: 51.2,
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

describe("PmiTab", () => {
  it("renders PMI indicators, weather vanes, and chart cards", () => {
    render(<PmiTab />);

    expect(screen.getByText("💡 采购经理人指数（PMI）景气区间与工业传导研判")).toBeInTheDocument();
    expect(screen.getByText("制造业处于扩张区间 (≥50)")).toBeInTheDocument();
    expect(screen.getByText("制造业 PMI (最新)")).toBeInTheDocument();
    expect(screen.getByText("非制造业 PMI (商务活动)")).toBeInTheDocument();
    expect(screen.getByText("综合经济动能评估")).toBeInTheDocument();
    expect(screen.getByText("双轮协同扩张")).toBeInTheDocument();
    expect(screen.getByText("PMI 采购经理人指数")).toBeInTheDocument();
  });
});
