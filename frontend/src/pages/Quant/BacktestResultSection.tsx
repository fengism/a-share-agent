import { lazy, Suspense } from "react";
import { ArrowLeftOutlined, LineChartOutlined } from "@ant-design/icons";
import { Button, Empty, Tag } from "antd";
import type { QuantBacktestRun } from "../../api/queries";
import QuantWorkspaceFallback from "./QuantWorkspaceFallback";
import { loadBacktestResult } from "./quantLazyLoaders";
import { quantStrategyLabel, quantUniverseLabel, QUANT_RUN_STATUS_META } from "./quantRun";

const BacktestResult = lazy(loadBacktestResult);

export default function BacktestResultSection({
  run,
  onBackToRuns,
}: {
  run?: QuantBacktestRun;
  onBackToRuns?: () => void;
}) {
  const hasResult = run?.status === "succeeded" && Boolean(run.result);

  return (
    <section className="quant-results-section" aria-label="回测结果分析">
      <div className="quant-section-heading">
        <div className="quant-section-heading-icon"><LineChartOutlined /></div>
        <div>
          <span>结果分析</span>
          <h2>收益、风险与交易表现</h2>
          <p>从核心指标、净值走势、回撤和成交记录复盘策略质量。</p>
        </div>
      </div>
      {run ? (
        <div className="quant-result-context">
          <div>
            <span>当前结果</span>
            <strong>{run.name}</strong>
            <small>
              {quantStrategyLabel(run.request.strategy ?? { type: "ma_cross" })} · {quantUniverseLabel(run)} · {run.request.start_date} 至 {run.request.end_date}
            </small>
          </div>
          <Tag>{QUANT_RUN_STATUS_META[run.status].label}</Tag>
          {onBackToRuns ? (
            <Button icon={<ArrowLeftOutlined />} onClick={onBackToRuns}>返回任务记录</Button>
          ) : null}
        </div>
      ) : null}
      {hasResult && run?.result ? (
        <Suspense fallback={<QuantWorkspaceFallback label="回测结果加载中" />}>
          <BacktestResult result={run.result} strategy={run.request.strategy} />
        </Suspense>
      ) : (
        <div className="quant-panel-empty">
          <Empty description={run ? "当前任务尚未生成可分析结果" : "请先创建或选择一个回测任务"} />
        </div>
      )}
    </section>
  );
}
