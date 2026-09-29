import { CopyOutlined, InfoCircleOutlined } from "@ant-design/icons";
import { Button, message } from "antd";
import type { QuantBacktestResult, QuantStrategyConfig } from "../../api/queries";
import BacktestCharts from "./results/BacktestCharts";
import BacktestMetrics from "./results/BacktestMetrics";
import BacktestTables from "./results/BacktestTables";
import BacktestTradeKline from "./results/BacktestTradeKline";
import { quantStrategyIdentity, quantStrategyParameterSummary } from "./quantRun";
import "./quant-results.css";

export default function BacktestResult({ result, strategy }: { result: QuantBacktestResult; strategy?: QuantStrategyConfig }) {
  const handleCopySummary = async () => {
    const lines = [
      "### 量化策略回测报告摘要",
      `- 策略：${strategy ? quantStrategyIdentity(strategy) : "自定义策略"}`,
      `- 标的：${result.codes.join(", ") || "多标的"}`,
      `- 累计总收益：${result.metrics.total_return != null ? `${result.metrics.total_return}%` : "-"}`,
      `- 年化收益率：${result.metrics.annualized_return != null ? `${result.metrics.annualized_return}%` : "-"}`,
      `- 最大回撤：${result.metrics.max_drawdown != null ? `${result.metrics.max_drawdown}%` : "-"}`,
      `- 夏普比率：${result.metrics.sharpe_ratio != null ? result.metrics.sharpe_ratio : "-"}`,
      `- 超额收益：${result.metrics.excess_return != null ? `${result.metrics.excess_return}%` : "-"}`,
      `- 交易笔数：${result.trades.length} 笔`,
    ];
    try {
      await navigator.clipboard.writeText(lines.join("\n"));
      message.success("回测摘要已复制到剪贴板");
    } catch {
      message.error("复制失败，请手动选择");
    }
  };

  return (
    <section aria-label="回测结果">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
        <nav className="quant-result-nav" aria-label="回测结果导航">
          <a href="#quant-result-metrics">核心指标</a>
          <a href="#quant-result-charts">净值与回撤</a>
          <a href="#quant-result-trades-chart">交易点位</a>
          <a href="#quant-result-details">收益与成交</a>
        </nav>
        <Button
          size="small"
          icon={<CopyOutlined />}
          onClick={handleCopySummary}
          aria-label="复制回测摘要"
        >
          复制摘要
        </Button>
      </div>
      {strategy ? (
        <div className="quant-result-strategy" aria-label="本次执行策略">
          <strong>{quantStrategyIdentity(strategy)}</strong>
          <span>{quantStrategyParameterSummary(strategy)}</span>
        </div>
      ) : null}
      {result.model_assumptions?.length ? (
        <aside className="quant-model-assumptions" aria-label="回测模型与适用边界">
          <div><InfoCircleOutlined aria-hidden="true" /><strong>日线近似模拟，历史表现不代表未来收益。</strong></div>
          <details>
            <summary>回测模型与适用边界</summary>
            <ul>{result.model_assumptions.map((item) => <li key={item}>{item}</li>)}</ul>
          </details>
        </aside>
      ) : null}
      <div id="quant-result-metrics" className="quant-result-anchor">
        <BacktestMetrics
          codes={result.codes}
          dataSources={result.data_sources}
          engineVersion={result.engine_version}
          metrics={result.metrics}
          holdoutValidation={result.holdout_validation}
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
