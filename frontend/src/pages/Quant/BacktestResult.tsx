import type { QuantBacktestResult, QuantStrategyConfig } from "../../api/queries";
import BacktestCharts from "./results/BacktestCharts";
import BacktestMetrics from "./results/BacktestMetrics";
import BacktestTables from "./results/BacktestTables";
import BacktestTradeKline from "./results/BacktestTradeKline";
import { quantStrategyIdentity, quantStrategyParameterSummary } from "./quantRun";
import "./quant-results.css";

export default function BacktestResult({ result, strategy }: { result: QuantBacktestResult; strategy?: QuantStrategyConfig }) {
  return (
    <section aria-label="回测结果">
      <nav className="quant-result-nav" aria-label="回测结果导航">
        <a href="#quant-result-metrics">核心指标</a>
        <a href="#quant-result-charts">净值与回撤</a>
        <a href="#quant-result-trades-chart">交易点位</a>
        <a href="#quant-result-details">收益与成交</a>
      </nav>
      {strategy ? (
        <div className="quant-result-strategy" aria-label="本次执行策略">
          <strong>{quantStrategyIdentity(strategy)}</strong>
          <span>{quantStrategyParameterSummary(strategy)}</span>
        </div>
      ) : null}
      <div id="quant-result-metrics" className="quant-result-anchor">
        <BacktestMetrics
          codes={result.codes}
          dataSources={result.data_sources}
          engineVersion={result.engine_version}
          metrics={result.metrics}
        />
      </div>
      <div id="quant-result-charts" className="quant-result-anchor">
        <BacktestCharts equityCurve={result.equity_curve} />
      </div>
      <div id="quant-result-trades-chart" className="quant-result-anchor">
        <BacktestTradeKline codes={result.codes} equityCurve={result.equity_curve} trades={result.trades} marketSnapshots={result.market_snapshots} />
      </div>
      <div id="quant-result-details" className="quant-result-anchor">
        <BacktestTables monthlyReturns={result.monthly_returns} trades={result.trades} />
      </div>
    </section>
  );
}
