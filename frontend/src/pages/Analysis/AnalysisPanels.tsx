import { lazy, Suspense } from "react";
import { Card, Skeleton } from "antd";
import ResponsiveSectionNav from "../../components/ResponsiveSectionNav";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import { useColors, useStyles } from "../../theme/hooks";
import type { AnalysisResult } from "../../types/stock";
import FundamentalPanel from "./FundamentalPanel";
import {
  loadFundFlowPanel,
  loadSentimentPanel,
  loadTechnicalPanel,
  loadValuationPanel,
} from "./analysisPanelLoaders";

const TechnicalPanel = lazy(loadTechnicalPanel);
const ValuationPanel = lazy(loadValuationPanel);
const SentimentPanel = lazy(loadSentimentPanel);
const FundFlowPanel = lazy(loadFundFlowPanel);
const ANALYSIS_PANEL_KEYS = ["fundamental", "technical", "valuation", "sentiment", "fundflow"] as const;

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
}: {
  code?: string;
  result: AnalysisResult | null | undefined;
  isExportingPdf: boolean;
}) {
  const colors = useColors();
  const { cardStyle } = useStyles();
  const [activePanelKey, setActivePanelKey] = useUrlSearchParam("panel", "fundamental", {
    allowedValues: ANALYSIS_PANEL_KEYS,
  });
  const panelItems = [
    { key: "fundamental", label: "基本面", children: code ? <FundamentalPanel code={code} analysis={result} /> : null },
    { key: "technical", label: "技术面", children: code ? <Suspense fallback={<PanelFallback />}><TechnicalPanel code={code} analysis={result} /></Suspense> : null },
    { key: "valuation", label: "估值面", children: code ? <Suspense fallback={<PanelFallback />}><ValuationPanel code={code} analysis={result} /></Suspense> : null },
    { key: "sentiment", label: "情绪面", children: code ? <Suspense fallback={<PanelFallback />}><SentimentPanel code={code} analysis={result} /></Suspense> : null },
    { key: "fundflow", label: "资金流向", children: code ? <Suspense fallback={<PanelFallback />}><FundFlowPanel code={code} /></Suspense> : null },
  ];

  return (
    <Card
      size="small"
      style={{ ...cardStyle, borderTop: `3px solid ${colors.primary}`, boxShadow: "0 1px 2px rgba(0,0,0,0.18)" }}
      styles={{ body: { padding: "10px 16px 14px", background: colors.nestedBg, borderRadius: 8 } }}
    >
      {isExportingPdf ? panelItems.map((item) => (
        <div key={item.key} className="pdf-section-block" style={{ marginTop: item.key === "fundamental" ? 0 : 20 }}>
          <div className="pdf-section-title" style={{ fontSize: 15, fontWeight: 700, color: colors.textPrimary, marginBottom: 12 }}>
            {item.label}
          </div>
          {item.children}
        </div>
      )) : (
        <ResponsiveSectionNav
          items={panelItems}
          activeKey={activePanelKey}
          onChange={setActivePanelKey}
          ariaLabel="个股分析维度"
          size="large"
          tabBarStyle={{ marginBottom: 18, borderBottom: `1px solid ${colors.border}`, fontWeight: 700 }}
        />
      )}
    </Card>
  );
}
