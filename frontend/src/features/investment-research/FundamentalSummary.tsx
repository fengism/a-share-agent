import { Card, Tag, Typography } from "antd";
import type { AnalysisResult } from "../../types/stock";
import { useColors, useStyles, semanticTagStyle } from "../../theme/hooks";
import type { SemanticTagColor } from "../../theme/hooks";
import AnalysisDimensionSummary from "./AnalysisDimensionSummary";

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

export default function FundamentalSummary({ fundamental }: { fundamental?: AnalysisResult["fundamental"] | null }) {
  const c = useColors();
  const { cardStyle, tagStyle } = useStyles();
  if (!fundamental) return null;

  return (
    <Card
      size="small"
      className="analysis-dimension-card"
      style={{ ...cardStyle, borderTop: `3px solid ${c.primary}55` }}
    >
      <AnalysisDimensionSummary label="基本面" score={fundamental.score}>
        <Paragraph className="analysis-dimension-summary__description">
          {fundamental.summary}
        </Paragraph>
        <div className="analysis-dimension-summary__groups">
          <div className="analysis-dimension-summary__group">
            <Text strong style={{ color: c.primary }}>核心优势</Text>
            <div className="analysis-dimension-summary__tags">
              {renderTags(fundamental.strengths, "primary", { ...tagStyle, margin: 0 })}
            </div>
          </div>
          <div className="analysis-dimension-summary__group">
            <Text strong style={{ color: c.up }}>主要风险</Text>
            <div className="analysis-dimension-summary__tags">
              {renderTags(fundamental.risks, "up", { ...tagStyle, margin: 0 })}
            </div>
          </div>
        </div>
      </AnalysisDimensionSummary>
    </Card>
  );
}
