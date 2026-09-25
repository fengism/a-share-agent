import { lazy, Suspense } from "react";
import { Card, Skeleton, Tabs } from "antd";
import { Link } from "react-router-dom";
import { buildStockProfileUrl } from "../../utils/stockLinks";
import { useColors, useStyles } from "../../theme/hooks";
import type { AnalysisResult } from "../../types/stock";
import { formatAnalysisDate } from "../../features/investment-research/analysisHistoryUrl";
import AIConclusion from "./AIConclusion";
import AnalysisDecisionBoard from "./AnalysisDecisionBoard";
import { loadResearchFrameworkPanel } from "./analysisPanelLoaders";

const ResearchFrameworkPanel = lazy(loadResearchFrameworkPanel);

export default function AnalysisResultSection({
  result,
  isExportingPdf,
  onOpenValuation,
}: {
  result: AnalysisResult | null | undefined;
  isExportingPdf: boolean;
  onOpenValuation?: () => void;
}) {
  const colors = useColors();
  const { cardStyle } = useStyles();
  if (!result) return null;

  const content = (
    <div className="analysis-research-conclusion">
      {!isExportingPdf && (
        <div className="analysis-result-context pdf-hide">
          <div className="analysis-result-context__identity">
            <strong>{result.stock_name || result.stock_code || "个股研究"}</strong>
            {result.stock_name && result.stock_code ? <span>{result.stock_code}</span> : null}
            <span>{result.analysis_date ? `分析日期 ${formatAnalysisDate(result.analysis_date)}` : "分析日期未记录"}</span>
          </div>
          {result.stock_code ? <Link to={buildStockProfileUrl(result.stock_code)}>查看个股资料 →</Link> : null}
        </div>
      )}
      <div className="analysis-research-overview">
        <AIConclusion result={result} embedded />
        <AnalysisDecisionBoard result={result} embedded />
      </div>
      <Suspense fallback={(
        <div aria-label="研究结论加载中" style={{ minHeight: 360, padding: 16 }}>
          <Skeleton active paragraph={{ rows: 8 }} />
        </div>
      )}>
        <ResearchFrameworkPanel analysis={result} forceFullReport={isExportingPdf} onOpenValuation={onOpenValuation} />
      </Suspense>
    </div>
  );

  return (
    <section id="analysis-result" tabIndex={-1} className="analysis-workspace__result" aria-label="个股分析结果">
      <Card
        className="analysis-result-card stock-research-report"
        style={{ ...cardStyle, borderTop: `3px solid ${colors.primary}` }}
        styles={{ body: { padding: "10px 16px 14px", background: colors.nestedBg, borderRadius: 8 } }}
      >
        {isExportingPdf ? (
          <>
            <div
              className="pdf-section-title"
              style={{ fontSize: "var(--c-font-lg)", fontWeight: "var(--c-weight-bold)", color: colors.textPrimary, marginBottom: 12 }}
            >
              研究结论
            </div>
            {content}
          </>
        ) : (
          <Tabs
            activeKey="research"
            size="large"
            tabBarStyle={{ marginBottom: 18, borderBottom: `1px solid ${colors.border}`, fontWeight: "var(--c-weight-bold)" }}
            items={[{ key: "research", label: "研究结论", children: content }]}
          />
        )}
      </Card>
    </section>
  );
}
