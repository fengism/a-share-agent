import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { QuantBacktestRun } from "../../api/queries";
import BacktestRunSummary from "./BacktestRunSummary";

const run: QuantBacktestRun = {
  id: "run-summary",
  name: "持仓 RSI 回测",
  status: "running",
  attempts: 2,
  created_at: 1_786_000_000,
  updated_at: 1_786_000_010,
  request: {
    name: "持仓 RSI 回测",
    universe: { source: "portfolio", codes: [] },
    strategy: {
      type: "rsi_reversion",
      version: "1.0.0",
      name: "RSI 均值回归",
      parameters: { rsi_period: 14, buy_threshold: 30, sell_threshold: 70 },
    },
    start_date: "2025-01-01",
    end_date: "2026-01-01",
    benchmark: "000300",
    execution: {
      initial_cash: 1_000_000,
      commission_rate: 0.0003,
      minimum_commission: 5,
      stamp_duty_rate: 0.0005,
      transfer_fee_rate: 0.00001,
      slippage_bps: 5,
      lot_size: 100,
      risk_free_rate: 0.015,
    },
  },
};

describe("BacktestRunSummary", () => {
  it("identifies the selected run and its request context", () => {
    render(<BacktestRunSummary run={run} />);

    expect(screen.getByText("当前回测")).toBeInTheDocument();
    expect(screen.getByText("持仓 RSI 回测")).toBeInTheDocument();
    expect(screen.getByText("运行中")).toBeInTheDocument();
    expect(screen.getByText("RSI 均值回归 · rsi_reversion@1.0.0")).toBeInTheDocument();
    expect(screen.getByText("rsi_period=14 · buy_threshold=30 · sell_threshold=70")).toBeInTheDocument();
    expect(screen.getByText("当前持仓")).toBeInTheDocument();
    expect(screen.getByText("2025-01-01 至 2026-01-01")).toBeInTheDocument();
    expect(screen.getByText("2 次")).toBeInTheDocument();
    expect(screen.getByText("1,000,000 元")).toBeInTheDocument();
    expect(screen.getByText(/佣金 3 BP/)).toHaveTextContent("印花税 5 BP");
    expect(screen.getByText("100 股")).toBeInTheDocument();
    expect(screen.getByText("1.5%")).toBeInTheDocument();
  });
});
