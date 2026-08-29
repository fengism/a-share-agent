import { Card, Tag, Typography } from "antd";
import type { AnalysisResult } from "../../types/stock";
import AnalysisDimensionSummary from "./AnalysisDimensionSummary";
import FinancialDataSections from "../../features/investment-research/FinancialDataSections";
import { useColors, useStyles, semanticTagStyle } from "../../theme/hooks";
import type { SemanticTagColor } from "../../theme/hooks";
import type { FundamentalExportData } from "../../types/stock";

interface Props {
  code: string;
  analysis?: AnalysisResult | null;
  isExportingPdf?: boolean;
  exportData?: FundamentalExportData;
}

const { Paragraph, Text } = Typography;

function renderTags(items: string[] | undefined, color: SemanticTagColor, tagStyle: React.CSSProperties) {
  if (!items || items.length === 0) {
    return <Text type="secondary">暂无</Text>;
  }

  return items.map((item) => (
    <Tag key={item} style={{ ...semanticTagStyle(color), ...tagStyle }}>
      {item}
    </Tag>
  ));
}


export default function FundamentalPanel({
  code,
  analysis,
  isExportingPdf = false,
  exportData,
}: Props) {
  const c = useColors();
  const { cardStyle, tagStyle } = useStyles();


  return (
    <div style={{ display: "grid", gap: 16, width: "100%", minWidth: 0, overflowX: "hidden" }}>
      {analysis?.fundamental && (
        <Card
          size="small"
          className="analysis-dimension-card"
          style={{ ...cardStyle, borderTop: `3px solid ${c.primary}55` }}
        >
          <AnalysisDimensionSummary label="基本面" score={analysis.fundamental.score}>
            <Paragraph className="analysis-dimension-summary__description">
              {analysis.fundamental.summary}
            </Paragraph>
            <div className="analysis-dimension-summary__groups">
              <div className="analysis-dimension-summary__group">
                <Text strong style={{ color: c.primary }}>核心优势</Text>
                <div className="analysis-dimension-summary__tags">
                  {renderTags(analysis.fundamental.strengths, "primary", { ...tagStyle, margin: 0 })}
                </div>
              </div>
              <div className="analysis-dimension-summary__group">
                <Text strong style={{ color: c.up }}>主要风险</Text>
                <div className="analysis-dimension-summary__tags">
                  {renderTags(analysis.fundamental.risks, "up", { ...tagStyle, margin: 0 })}
                </div>
              </div>
            </div>
          </AnalysisDimensionSummary>
        </Card>
      )}

      <FinancialDataSections code={code} isExportingPdf={isExportingPdf} exportData={exportData} />
    </div>
  );
}
