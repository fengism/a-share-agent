import { lazy, Suspense } from "react";
import { Card, Skeleton } from "antd";
import { Navigate, useSearchParams } from "react-router-dom";
import { buildStockValuationUrl } from "../../features/investment-research/analysisHistoryUrl";
import { useColors, useStyles } from "../../theme/hooks";
import type { AnalysisResult, FundamentalExportData } from "../../types/stock";
import FundamentalPanel from "./FundamentalPanel";
import { loadValuationPanel } from "./analysisPanelLoaders";

const ValuationPanel = lazy(loadValuationPanel);

function PanelFallback() {
  return (
    <div aria-label="分析面板加载中" style={{ minHeight: 360, padding: 16 }}>
      <Skeleton active paragraph={{ rows: 8 }} />
    </div>
  );
}

export default function AnalysisPanels({
  code,
  result,
  isExportingPdf,
  financialExportData,
}: {
  code?: string;
  result: AnalysisResult | null | undefined;
  isExportingPdf: boolean;
  financialExportData?: FundamentalExportData;
}) {
  const [searchParams] = useSearchParams();
  const colors = useColors();
  const { cardStyle } = useStyles();
  const exportItems = [
    {
      key: "fundamental",
      label: "基本面",
      children: code ? (
        <FundamentalPanel
          code={code}
          analysis={result}
          isExportingPdf={isExportingPdf}
          exportData={financialExportData}
        />
      ) : null,
    },
    { key: "valuation", label: "估值面", children: code ? <Suspense fallback={<PanelFallback />}><ValuationPanel code={code} /></Suspense> : null },
  ];

  if (!isExportingPdf && code && searchParams.get("panel") === "valuation") {
    return <Navigate to={buildStockValuationUrl(code, searchParams.get("date"))} replace />;
  }

  if (!isExportingPdf || !code) return null;

  return (
    <Card
      size="small"
      className="analysis-export-panels stock-research-report"
      style={{ ...cardStyle, borderTop: `3px solid ${colors.primary}` }}
      styles={{ body: { padding: "10px 16px 14px", background: colors.nestedBg, borderRadius: 8 } }}
    >
      {exportItems.map((item) => (
        <div
          key={item.key}
          className="pdf-section-block"
          data-pdf-capture
          data-pdf-group={item.key === "fundamental" ? undefined : true}
          style={{ marginTop: item.key === "fundamental" ? 0 : 20 }}
        >
          <div
            className="pdf-section-title"
            data-pdf-group={item.key === "fundamental" ? true : undefined}
            style={{ fontSize: "var(--c-font-lg)", fontWeight: "var(--c-weight-bold)", color: colors.textPrimary, marginBottom: 12 }}
          >
            {item.label}
          </div>
          {item.children}
        </div>
      ))}
    </Card>
  );
}
