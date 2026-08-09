import { memo } from "react";
import { Alert, Card } from "antd";
import { useAnalysisStore } from "../../store/analysisStore";
import { useColors, useStyles } from "../../theme/hooks";
import type { AnalysisResult } from "../../types/stock";
import AIConclusion from "./AIConclusion";
import AnalysisProgressSteps from "./AnalysisProgressSteps";
import SkeletonAIConclusion from "./SkeletonAIConclusion";

interface AnalysisStateSectionProps {
  isAnalyzing: boolean;
  result: AnalysisResult | null | undefined;
  error: string | null;
}

export default memo(function AnalysisStateSection({
  isAnalyzing,
  result,
  error,
}: AnalysisStateSectionProps) {
  const stages = useAnalysisStore((state) => state.analysisStages);
  const currentStageIndex = useAnalysisStore((state) => state.currentStageIndex);
  const colors = useColors();
  const { cardStyle, sectionCardBodyStyle } = useStyles();

  return (
    <>
      {isAnalyzing && (
        <Card size="small" style={{ ...cardStyle, marginBottom: 16 }} styles={{ body: sectionCardBodyStyle }}>
          <AnalysisProgressSteps stages={stages} currentStageIndex={currentStageIndex} />
        </Card>
      )}
      {(result || isAnalyzing) && (
        <div
          className="pdf-avoid-break"
          style={{
            marginBottom: 12,
            borderLeft: "4px solid transparent",
            borderImage: `linear-gradient(180deg, ${colors.primary}, ${colors.accent}) 1`,
            background: colors.nestedBg,
            borderRadius: 8,
            padding: 4,
          }}
        >
          {result ? <AIConclusion result={result} /> : <SkeletonAIConclusion />}
        </div>
      )}
      {error && !isAnalyzing && (
        <Alert
          message={`分析失败: ${error}`}
          type="error"
          showIcon
          closable
          style={{ marginBottom: 16, borderRadius: 8 }}
        />
      )}
      {result?.technical && (
        <Card
          size="small"
          className="pdf-avoid-break"
          style={{ ...cardStyle, marginBottom: 12, borderTop: `3px solid ${colors.primary}`, boxShadow: "0 1px 2px rgba(0,0,0,0.18)" }}
          styles={{ body: { padding: "12px 16px" } }}
        >
          <div className="metric-grid cols-3v" style={{ gap: 12 }}>
            <div style={{ padding: "10px 12px", background: colors.elevatedBg, border: `1px solid ${colors.border}`, borderRadius: 8 }}>
              <div style={{ fontSize: 12, color: colors.textSecondary, marginBottom: 6 }}>技术结论</div>
              <div style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 1.8 }}>{result.technical.summary}</div>
            </div>
            <div style={{ padding: "10px 12px", background: colors.elevatedBg, border: `1px solid ${colors.border}`, borderRadius: 8 }}>
              <div style={{ fontSize: 12, color: colors.textSecondary, marginBottom: 6 }}>趋势判断</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: colors.textPrimary }}>{result.technical.trend || "-"}</div>
            </div>
            <div style={{ padding: "10px 12px", background: colors.elevatedBg, border: `1px solid ${colors.border}`, borderRadius: 8 }}>
              <div style={{ fontSize: 12, color: colors.textSecondary, marginBottom: 6 }}>关键位</div>
              <div style={{ fontSize: 13, color: colors.textSecondary, lineHeight: 1.8 }}>
                支撑 {result.technical.support_level?.toFixed(2) ?? "-"} / 压力 {result.technical.resistance_level?.toFixed(2) ?? "-"}
              </div>
            </div>
          </div>
        </Card>
      )}
    </>
  );
});
