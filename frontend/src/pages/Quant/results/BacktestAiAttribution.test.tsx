import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import type { QuantBacktestResult } from "../../../api/queries";
import BacktestAiAttribution from "./BacktestAiAttribution";

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

const mockResult: QuantBacktestResult = {
  engine_version: "v1",
  data_hash: "hash-123",
  data_sources: ["akshare"],
  codes: ["600519", "000858"],
  metrics: {
    total_return: 28.5,
    annualized_return: 25.1,
    annualized_volatility: 12.0,
    benchmark_return: 6.2,
    calmar_ratio: 3.2,
    excess_return: 22.3,
    max_drawdown: -8.8,
    profit_loss_ratio: 2.1,
    sharpe_ratio: 1.85,
    trade_count: 14,
    turnover_rate: 180,
    win_rate: 64.3,
    alpha: 8.5,
  },
  equity_curve: [],
  monthly_returns: [],
  trades: [],
};

describe("BacktestAiAttribution", () => {
  it("renders AI tactical diagnosis with score, archetype and multi-factor insights", () => {
    renderWithClient(
      <BacktestAiAttribution
        result={mockResult}
        strategy={{
          type: "turnover_momentum",
          version: "1.0.0",
          name: "换手量价动量突破",
          parameters: { mom_period: 10, min_turnover: 2 },
        }}
      />
    );

    expect(screen.getByText(/AI 策略战术归因与多因子体检/)).toBeInTheDocument();
    expect(screen.getByText("策略成色综合评级")).toBeInTheDocument();
    expect(screen.getByText(/换手率与量价活跃度归因/)).toBeInTheDocument();
    expect(screen.getByText(/资金流向与主力博弈协同建议/)).toBeInTheDocument();
    expect(screen.getByText(/财报基本面与选股池质量底座/)).toBeInTheDocument();
    expect(screen.getByText("超额阿尔法强劲")).toBeInTheDocument();
    expect(screen.getByText("回撤控制扎实")).toBeInTheDocument();
  });

  it("supports copying AI attribution report to clipboard", async () => {
    const writeTextSpy = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: {
        writeText: writeTextSpy,
      },
    });

    renderWithClient(<BacktestAiAttribution result={mockResult} />);

    const copyBtn = screen.getByRole("button", { name: "复制AI归因报告" });
    fireEvent.click(copyBtn);

    expect(writeTextSpy).toHaveBeenCalledWith(expect.stringContaining("### AI 策略战术归因体检报告"));
    expect(writeTextSpy).toHaveBeenCalledWith(expect.stringContaining("综合成色评分"));
    expect(writeTextSpy).toHaveBeenCalledWith(expect.stringContaining("换手与资金流建议"));
  });

  it("handles batch adding backtest codes to watchlist", async () => {
    renderWithClient(<BacktestAiAttribution result={mockResult} />);

    const addBtn = screen.getByRole("button", { name: "批量加自选" });
    expect(addBtn).toBeInTheDocument();
    fireEvent.click(addBtn);

    await waitFor(() => {
      expect(screen.getByText(/已加入自选/)).toBeInTheDocument();
    });
  });
});
