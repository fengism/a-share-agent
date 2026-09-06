import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { describe, expect, it } from "vitest";
import type { AnalysisResult } from "../../types/stock";
import AnalysisDecisionBoard from "./AnalysisDecisionBoard";

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname}{location.search}</span>;
}

describe("AnalysisDecisionBoard", () => {
  it("renders a conditional action and hands a follow-up to Chat", () => {
    const result = {
      stock_code: "600519",
      stock_name: "贵州茅台",
      signal: "hold",
      current_price: 1520,
      technical: { support_level: 1450, resistance_level: 1650 },
    } as AnalysisResult;

    render(
      <MemoryRouter initialEntries={["/analysis/600519"]}>
        <AnalysisDecisionBoard result={result} />
        <LocationProbe />
      </MemoryRouter>,
    );

    expect(screen.getByText("观察")).toBeInTheDocument();
    expect(screen.queryByLabelText("关键点位")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /失效条件/ }));
    expect(screen.getByTestId("location").textContent).toContain("/chat?prompt=");
    expect(decodeURIComponent(screen.getByTestId("location").textContent || "")).toContain("贵州茅台当前结论的失效条件是什么");
  });

  it("prefers role-specific research actions", () => {
    const result = {
      stock_code: "600519",
      stock_name: "贵州茅台",
      signal: "buy",
      current_price: 1520,
      technical: { support_level: 1450, resistance_level: 1650 },
      research_framework: {
        actions: {
          new_investor_action: "avoid",
          holder_action: "reduce",
          rationale: "当前估值没有覆盖主要下行情景",
          buy_or_add_range: null,
          add_triggers: [],
          sell_triggers: ["现金流恶化"],
          thesis_breakers: ["品牌定价权持续削弱"],
          monitoring_metrics: [],
        },
      },
    } as unknown as AnalysisResult;

    render(
      <MemoryRouter>
        <AnalysisDecisionBoard result={result} />
      </MemoryRouter>,
    );

    expect(screen.getByText("暂时回避")).toBeInTheDocument();
    expect(screen.getByText("当前估值没有覆盖主要下行情景")).toBeInTheDocument();
    expect(screen.getByText(/已持有者：/)).toHaveTextContent("考虑减持");
    expect(screen.getByText(/首要失效条件/)).toHaveTextContent("品牌定价权持续削弱");
  });
});
