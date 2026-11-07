import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import FinancialMetric from "./FinancialMetric";

vi.mock("../theme/hooks", () => ({
  useColors: () => ({
    textPrimary: "#ffffff",
    textSecondary: "#8b949e",
    up: "#f5222d",
    down: "#52c41a",
  }),
}));

describe("FinancialMetric", () => {
  it("renders label, value, and unit correctly", () => {
    render(
      <FinancialMetric
        label="总市值"
        value="1,850.25"
        unit="亿元"
      />,
    );

    expect(screen.getByText("总市值")).toBeInTheDocument();
    expect(screen.getByText("1,850.25")).toBeInTheDocument();
    expect(screen.getByText("亿元")).toBeInTheDocument();
  });

  it("applies up color when change is positive", () => {
    render(
      <FinancialMetric
        label="最新价"
        value="1520.00"
        change={2.35}
        unit="元"
      />,
    );

    const valEl = screen.getByText("1520.00");
    expect(valEl).toHaveClass("financial-metric__value--up");
    expect(screen.getByText("+2.35%")).toBeInTheDocument();
  });

  it("applies down color when change is negative", () => {
    render(
      <FinancialMetric
        label="最新价"
        value="1480.00"
        change={-1.5}
      />,
    );

    const valEl = screen.getByText("1480.00");
    expect(valEl).toHaveClass("financial-metric__value--down");
    expect(screen.getByText("-1.50%")).toBeInTheDocument();
  });

  it("renders null fallback as --", () => {
    render(
      <FinancialMetric
        label="市盈率(TTM)"
        value={null}
      />,
    );

    expect(screen.getByText("--")).toBeInTheDocument();
  });
});
