import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ConstituentPerformanceMatrix from "./ConstituentPerformanceMatrix";

const mockTrades = [
  {
    date: "2026-01-02",
    code: "600519",
    side: "buy" as const,
    price: 1500,
    shares: 100,
    amount: 150000,
    fee: 45,
    realized_pnl: null,
  },
  {
    date: "2026-01-15",
    code: "600519",
    side: "sell" as const,
    price: 1650,
    shares: 100,
    amount: 165000,
    fee: 49.5,
    realized_pnl: 15000,
  },
  {
    date: "2026-01-05",
    code: "000858",
    side: "buy" as const,
    price: 140,
    shares: 500,
    amount: 70000,
    fee: 21,
    realized_pnl: null,
  },
  {
    date: "2026-01-20",
    code: "000858",
    side: "sell" as const,
    price: 135,
    shares: 500,
    amount: 67500,
    fee: 20.25,
    realized_pnl: -2500,
  },
];

describe("ConstituentPerformanceMatrix", () => {
  it("renders performance breakdown for multiple constituent stocks", () => {
    render(
      <ConstituentPerformanceMatrix
        codes={["600519", "000858"]}
        trades={mockTrades}
      />
    );

    expect(screen.getByText("多标的盈亏贡献与胜负分析 (Constituent Stock Performance)")).toBeInTheDocument();
    expect(screen.getByText("2 只标的")).toBeInTheDocument();
    expect(screen.getByText("最佳盈利贡献标的 (Alpha King)")).toBeInTheDocument();
    expect(screen.getByText("+15000.00元")).toBeInTheDocument();

    // Stock codes in table
    expect(screen.getByRole("link", { name: "查看600519研报" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看000858研报" })).toBeInTheDocument();
  });

  it("returns null when only single stock with no trades", () => {
    const { container } = render(
      <ConstituentPerformanceMatrix
        codes={["600519"]}
        trades={[]}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });
});
