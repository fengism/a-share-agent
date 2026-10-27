import { describe, expect, it, vi } from "vitest";
import { exportBacktestTearsheetMarkdown, exportEquityCurveCsv } from "./exportTearsheet";
import type { QuantBacktestResult } from "../../../api/queries";

describe("exportTearsheet", () => {
  it("generates and triggers download of tearsheet markdown and equity curve csv", () => {
    let downloadedFilename = "";

    const originalCreateObjectURL = URL.createObjectURL;

    URL.createObjectURL = vi.fn().mockImplementation(() => {
      return "blob:http://localhost/fake-blob-url";
    });

    const clickMock = vi.fn();
    const createElementSpy = vi.spyOn(document, "createElement").mockImplementation((tagName: string) => {
      const el = document.createElementNS("http://www.w3.org/1999/xhtml", tagName) as unknown as HTMLElement;
      if (tagName === "a") {
        el.click = clickMock;
        Object.defineProperty(el, "download", {
          set: (val: string) => { downloadedFilename = val; },
          get: () => downloadedFilename,
        });
      }
      return el;
    });

    const mockResult: QuantBacktestResult = {
      engine_version: "2026-09-19-v10",
      data_hash: "hash123",
      data_sources: ["akshare-daily"],
      codes: ["600519", "000858"],
      metrics: {
        total_return: 35.8,
        annualized_return: 22.4,
        annualized_volatility: 16.5,
        benchmark_return: 10.2,
        excess_return: 25.6,
        sharpe_ratio: 1.35,
        sortino_ratio: 1.82,
        calmar_ratio: 2.1,
        omega_ratio: 1.55,
        alpha: 15.2,
        beta: 0.85,
        treynor_ratio: 0.24,
        upside_capture: 110.5,
        downside_capture: 65.2,
        max_drawdown: -10.6,
        max_drawdown_duration_days: 45,
        win_rate: 62.5,
        profit_loss_ratio: 1.95,
        turnover_rate: 80.0,
        trade_count: 12,
        closed_trade_count: 10,
        observation_count: 242,
        probabilistic_sharpe_ratio: 98.5,
        deflated_sharpe_ratio: 96.2,
        stress_tests: {
          "2024微盘挤兑": { return_pct: 5.2, max_drawdown_pct: -6.4 },
        },
      },
      equity_curve: [
        { date: "2024-01-02", equity: 1000000, benchmark: 1000000, drawdown: 0 },
        { date: "2024-01-03", equity: 1020000, benchmark: 1010000, drawdown: 0 },
      ],
      monthly_returns: [
        { month: "2024-01", return_pct: 4.5 },
      ],
      trades: [],
    };

    exportBacktestTearsheetMarkdown(mockResult, {
      type: "ma_cross",
      version: "1.0.0",
      parameters: { fast_period: 5, slow_period: 20 },
    });

    expect(clickMock).toHaveBeenCalled();
    expect(downloadedFilename).toContain("量化策略研报_ma_cross_");

    exportEquityCurveCsv(mockResult.equity_curve);
    expect(downloadedFilename).toContain("量化每日净值序列_");

    createElementSpy.mockRestore();
    URL.createObjectURL = originalCreateObjectURL;
  });
});
