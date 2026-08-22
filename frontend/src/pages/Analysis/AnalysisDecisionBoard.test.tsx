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
  it("renders conditional action, key levels and hands a follow-up to Chat", () => {
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
    expect(screen.getByText("1450.00")).toBeInTheDocument();
    expect(screen.getByText("1650.00")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /失效条件/ }));
    expect(screen.getByTestId("location").textContent).toContain("/chat?prompt=");
    expect(decodeURIComponent(screen.getByTestId("location").textContent || "")).toContain("贵州茅台当前结论的失效条件是什么");
  });
});
