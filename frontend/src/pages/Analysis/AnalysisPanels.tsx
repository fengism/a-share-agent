import { lazy, Suspense } from "react";
import { Card, Skeleton } from "antd";
import ResponsiveSectionNav from "../../components/ResponsiveSectionNav";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import { useColors, useStyles } from "../../theme/hooks";
import type { AnalysisResult, FundamentalExportData } from "../../types/stock";
import AIConclusion from "./AIConclusion";
import AnalysisDecisionBoard from "./AnalysisDecisionBoard";
import FundamentalPanel from "./FundamentalPanel";
import {
  loadFundFlowPanel,
  loadResearchFrameworkPanel,
  loadSentimentPanel,
  loadTechnicalPanel,
  loadValuationPanel,
} from "./analysisPanelLoaders";

const ResearchFrameworkPanel = lazy(loadResearchFrameworkPanel);
const TechnicalPanel = lazy(loadTechnicalPanel);
const ValuationPanel = lazy(loadValuationPanel);
const SentimentPanel = lazy(loadSentimentPanel);
const FundFlowPanel = lazy(loadFundFlowPanel);
const ANALYSIS_PANEL_KEYS = ["research", "fundamental", "technical", "valuation", "sentiment", "fundflow"] as const;

function preload(loader: () => Promise<unknown>) {
  void loader().catch(() => undefined);
}

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
  const colors = useColors();
  const { cardStyle } = useStyles();
  const [activePanelKey, setActivePanelKey] = useUrlSearchParam("panel", "research", {
    allowedValues: ANALYSIS_PANEL_KEYS,
  });
  const panelItems = [
    {
      key: "research",
      label: "研究结论",
      onIntent: () => preload(loadResearchFrameworkPanel),
      children: code ? (
        <div className="analysis-research-conclusion">
          {result ? (
            <div className="analysis-research-overview">
              <AIConclusion result={result} embedded />
              <AnalysisDecisionBoard result={result} embedded />
            </div>
          ) : null}
          <Suspense fallback={<PanelFallback />}>
            <ResearchFrameworkPanel analysis={result} forceFullReport={isExportingPdf} />
          </Suspense>
        </div>
      ) : null,
    },
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
    { key: "technical", label: "技术面", onIntent: () => preload(loadTechnicalPanel), children: code ? <Suspense fallback={<PanelFallback />}><TechnicalPanel code={code} analysis={result} /></Suspense> : null },
    { key: "valuation", label: "估值面", onIntent: () => preload(loadValuationPanel), children: code ? <Suspense fallback={<PanelFallback />}><ValuationPanel code={code} analysis={result} /></Suspense> : null },
    { key: "sentiment", label: "情绪面", onIntent: () => preload(loadSentimentPanel), children: code ? <Suspense fallback={<PanelFallback />}><SentimentPanel code={code} analysis={result} /></Suspense> : null },
    { key: "fundflow", label: "资金流向", onIntent: () => preload(loadFundFlowPanel), children: code ? <Suspense fallback={<PanelFallback />}><FundFlowPanel code={code} isExportingPdf={isExportingPdf} /></Suspense> : null },
  ];

  return (
    <Card
      size="small"
      className="analysis-panels-card stock-research-report"
      style={{ ...cardStyle, borderTop: `3px solid ${colors.primary}` }}
      styles={{ body: { padding: "10px 16px 14px", background: colors.nestedBg, borderRadius: 8 } }}
    >
      {isExportingPdf ? panelItems.map((item) => (
        <div
          key={item.key}
          className="pdf-section-block"
          data-pdf-capture={item.key === "research" ? undefined : true}
          data-pdf-group={item.key === "fundamental" ? undefined : true}
          style={{ marginTop: item.key === "research" ? 0 : 20 }}
        >
          <div
            className="pdf-section-title"
            data-pdf-group={item.key === "fundamental" ? true : undefined}
            style={{ fontSize: 15, fontWeight: 700, color: colors.textPrimary, marginBottom: 12 }}
          >
            {item.label}
          </div>
          {item.children}
        </div>
      )) : (
        <ResponsiveSectionNav
          items={panelItems}
          activeKey={activePanelKey}
          onChange={setActivePanelKey}
          ariaLabel="个股研究维度"
          size="large"
          tabBarStyle={{ marginBottom: 18, borderBottom: `1px solid ${colors.border}`, fontWeight: 700 }}
        />
      )}
    </Card>
  );
}
