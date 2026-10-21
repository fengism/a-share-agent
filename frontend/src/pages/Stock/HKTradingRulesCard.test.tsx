import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import HKTradingRulesCard from "./HKTradingRulesCard";

describe("HKTradingRulesCard", () => {
  it("renders HK trading rules and mechanism details", () => {
    render(<HKTradingRulesCard />);

    expect(screen.getByRole("heading", { name: "港股交易规则" })).toBeInTheDocument();
    expect(screen.getByText("香港证券市场交易机制速览")).toBeInTheDocument();
    expect(screen.getByText("T+0 回转交易 · 无单日涨跌幅限制")).toBeInTheDocument();
    expect(screen.getByText("早盘 09:30-12:00 · 午盘 13:00-16:00")).toBeInTheDocument();
    expect(screen.getByText("T+2 证券及资金结算 · 港币 (HKD) 报价")).toBeInTheDocument();
  });
});
