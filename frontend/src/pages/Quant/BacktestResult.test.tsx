import { render, screen } from "@testing-library/react";
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import type { ComponentProps } from "react";
import type { QuantBacktestResult } from "../../api/queries";
import BacktestResult from "./BacktestResult";

vi.mock("../../hooks/useMediaQuery", () => ({ useMediaQuery: () => true }));
vi.mock("./results/BacktestTradeKline", () => ({
  default: () => <div data-testid="backtest-trade-kline">交易点位K线</div>,
}));
vi.mock("echarts-for-react/lib/core", () => ({
  default: (props: ComponentProps<"div"> & { "data-testid"?: string }) => (
    <div data-testid={props["data-testid"]} style={props.style} />
  ),
}));

const nativeGetComputedStyle = window.getComputedStyle.bind(window);

beforeAll(() => {
  vi.spyOn(window, "getComputedStyle").mockImplementation((element) => nativeGetComputedStyle(element));
});

afterAll(() => {
  vi.restoreAllMocks();
});

function makeResult(overrides: Partial<QuantBacktestResult> = {}): QuantBacktestResult {
  return {
    engine_version: "v1",
    data_hash: "hash",
    data_sources: ["akshare"],
    codes: ["600519"],
    metrics: {
      total_return: 12.34,
      annualized_return: 11.2,
      annualized_volatility: 10,
      benchmark_return: 8,
      calmar_ratio: 2.15,
      downside_volatility: 7.5,
      excess_return: 4.34,
      information_ratio: 0.72,
      max_drawdown: -5.2,
      profit_loss_ratio: 1.8,
      sharpe_ratio: 1.1,
      sortino_ratio: 1.46,
      tracking_error: 6.03,
      turnover_rate: 100,
      trade_count: 1,
      win_rate: 60,
    },
    equity_curve: [{ date: "2026-01-01", equity: 1.12, benchmark: 1.08, drawdown: -0.03 }],
    monthly_returns: [{ month: "2026-01", return_pct: 2.5 }],
    trades: [{
      date: "2026-01-02",
      code: "600519",
      side: "buy",
      price: 1500,
      shares: 100,
      amount: 150_000,
      fee: 45,
      realized_pnl: null,
    }],
    ...overrides,
  };
}

describe("BacktestResult", () => {
  it("renders metrics, compact charts and result tables", () => {
    render(<BacktestResult result={makeResult()} />);

    expect(screen.getByRole("region", { name: "回测结果" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "回测结果导航" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "核心指标" })).toHaveAttribute("href", "#quant-result-metrics");
    expect(screen.getByRole("link", { name: "净值与回撤" })).toHaveAttribute("href", "#quant-result-charts");
    expect(screen.getByRole("link", { name: "交易点位" })).toHaveAttribute("href", "#quant-result-trades-chart");
    expect(screen.getByRole("link", { name: "收益与成交" })).toHaveAttribute("href", "#quant-result-details");
    expect(screen.getByText("总收益")).toBeInTheDocument();
    expect(screen.getByText("总收益").closest(".ant-statistic")).toHaveTextContent("12.34%");
    expect(screen.getByText("基准收益")).toBeInTheDocument();
    expect(screen.getByText("索提诺比率").closest(".ant-statistic")).toHaveTextContent("1.46");
    expect(screen.getByText("卡玛比率").closest(".ant-statistic")).toHaveTextContent("2.15");
    expect(screen.getByText("信息比率").closest(".ant-statistic")).toHaveTextContent("0.72");
    expect(screen.getByText("下行波动").closest("tr")).toHaveTextContent("7.50%");
    expect(screen.getByText("跟踪误差").closest("tr")).toHaveTextContent("6.03%");
    expect(screen.getByText("1 次")).toBeInTheDocument();
    expect(screen.getByText("akshare")).toBeInTheDocument();
    expect(screen.getByText("v1")).toBeInTheDocument();
    expect(screen.getByTestId("equity-chart")).toHaveStyle({ height: "260px" });
    expect(screen.getByTestId("drawdown-chart")).toHaveStyle({ height: "260px" });
    expect(screen.getByTestId("backtest-trade-kline")).toBeInTheDocument();
    expect(screen.getByText("2026-01")).toBeInTheDocument();
    expect(screen.getByText("买入")).toBeInTheDocument();
  });

  it("shows clear empty states for charts and detail tables", () => {
    render(<BacktestResult result={makeResult({ equity_curve: [], monthly_returns: [], trades: [] })} />);

    expect(screen.getByText("暂无净值数据")).toBeInTheDocument();
    expect(screen.getByText("暂无回撤数据")).toBeInTheDocument();
    expect(screen.getByText("暂无月度收益")).toBeInTheDocument();
    expect(screen.getByText("暂无成交记录")).toBeInTheDocument();
    expect(screen.queryByTestId("equity-chart")).not.toBeInTheDocument();
  });

  it("warns when a legacy result has no benchmark return", () => {
    const result = makeResult();
    result.metrics.benchmark_return = null;
    result.metrics.excess_return = null;

    render(<BacktestResult result={result} />);

    expect(screen.getByText("该回测没有可用的基准收益")).toBeInTheDocument();
    expect(screen.getByText(/建议重新创建回测/)).toBeInTheDocument();
  });

  it("renders independent holdout validation metrics when available", () => {
    render(<BacktestResult result={makeResult({
      holdout_validation: {
        method: "holdout",
        start_date: "2025-09-01",
        end_date: "2025-12-31",
        training_ratio: 2 / 3,
        observation_count: 20,
        metrics: {
          total_return: 3.4,
          annualized_return: 9.2,
          annualized_volatility: 11,
          benchmark_return: 2.5,
          calmar_ratio: 1.7,
          downside_volatility: 6.8,
          excess_return: 0.9,
          information_ratio: 0.4,
          max_drawdown: -2,
          profit_loss_ratio: 1.4,
          sharpe_ratio: 0.8,
          sortino_ratio: 1.2,
          tracking_error: 4,
          turnover_rate: 30,
          trade_count: 2,
          win_rate: 50,
        },
      },
    })} />);

    expect(screen.getByText("后段样本验证")).toBeInTheDocument();
    expect(screen.getByText("独立资金")).toBeInTheDocument();
    expect(screen.getByText("2025-09-01 至 2025-12-31")).toBeInTheDocument();
    expect(screen.getByText("20 个")).toBeInTheDocument();
  });

  it("labels the exact strategy used for the result", () => {
    render(<BacktestResult
      result={makeResult()}
      strategy={{
        type: "bias_reversal",
        version: "1.0.0",
        name: "BIAS 乖离率反转",
        parameters: { period: 6, buy_threshold: -3, sell_threshold: 3 },
      }}
    />);

    expect(screen.getByLabelText("本次执行策略")).toHaveTextContent("BIAS 乖离率反转 · bias_reversal@1.0.0");
    expect(screen.getByLabelText("本次执行策略")).toHaveTextContent("period=6 · buy_threshold=-3 · sell_threshold=3");
  });

});
