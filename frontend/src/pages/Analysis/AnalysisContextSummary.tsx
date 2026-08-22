import { Progress } from "antd";
import type { AnalysisPageData, AnalysisResult } from "../../types/stock";
import { getConditionalAction } from "./analysisDecision";

interface Props {
  pageData?: AnalysisPageData;
  result?: AnalysisResult | null;
}

export default function AnalysisContextSummary({ pageData, result }: Props) {
  const sentimentScore = Math.max(0, Math.min(100, Math.round((result?.sentiment.score ?? 5) * 10)));
  const confidence = Math.round((result?.confidence ?? 0) * 100);
  const unavailable = pageData?.unavailable_sections?.length ?? 0;
  const completeness = Math.max(0, 100 - unavailable * 20);
  const action = result ? getConditionalAction(result.signal) : null;
  const riskLevel = !result
    ? "等待分析"
    : result.risk_warnings.length >= 4 || result.overall_rating < 4
      ? "较高"
      : result.risk_warnings.length >= 2
        ? "中等"
        : "可控";

  return (
    <section className="analysis-context-summary u-card" aria-label="分析上下文">
      <div className="analysis-context-summary__sentiment">
        <div className="analysis-context-summary__sentiment-copy">
          <span className="analysis-context-card__eyebrow">AI 市场情绪</span>
          <strong>{result?.sentiment.market_mood || "中性"}</strong>
          <small>综合市场情绪与分析结论</small>
        </div>
        <div className="analysis-context-summary__sentiment-score" aria-label={`市场情绪评分 ${sentimentScore}`}>
          <strong>{sentimentScore}</strong><span>/100</span>
        </div>
      </div>

      <div className="analysis-context-summary__quality">
        <span className="analysis-context-card__eyebrow">决策质量</span>
        <div className="analysis-context-summary__metrics">
          <div className="analysis-context-metric"><span>行动语言</span><strong className={`is-${action?.tone ?? "neutral"}`}>{action?.label ?? "等待"}</strong></div>
          <div className="analysis-context-metric"><span>风险等级</span><strong>{riskLevel}</strong></div>
        </div>
        <div className="analysis-context-summary__progress">
          <div className="analysis-context-progress"><span>模型置信度 {confidence}%</span><Progress percent={confidence} showInfo={false} size="small" /></div>
          <div className="analysis-context-progress"><span>数据完整度 {completeness}%</span><Progress percent={completeness} showInfo={false} size="small" status={completeness < 80 ? "exception" : "normal"} /></div>
        </div>
      </div>
    </section>
  );
}
