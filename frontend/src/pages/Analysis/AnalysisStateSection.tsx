import { memo } from "react";
import { Alert, Card } from "antd";
import { useAnalysisStore } from "../../store/analysisStore";
import { useColors, useStyles, useTokens } from "../../theme/hooks";
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
  const t = useTokens();
  const { cardStyle } = useStyles();

  return (
    <>
      {(isAnalyzing || error) && stages.length > 0 && (
        <AnalysisProgressSteps
          stages={stages}
          currentStageIndex={currentStageIndex}
          status={error ? "error" : "running"}
        />
      )}
      {(result || isAnalyzing) && (
        result ? <AIConclusion result={result} /> : <SkeletonAIConclusion />
      )}
      {error && !isAnalyzing && (
        <Alert
          message={`分析失败: ${error}`}
          type="error"
          showIcon
          closable
          style={{ marginBottom: t.space[4], borderRadius: t.radius.md }}
        />
      )}
      {result?.technical && (
        <Card
          size="small"
          className="pdf-avoid-break"
          style={{ ...cardStyle, marginBottom: t.space[3], borderTop: `3px solid ${colors.primary}`, boxShadow: t.shadow.xs }}
          styles={{ body: { padding: `${t.space[3]} ${t.space[4]}` } }}
        >
          <div className="metric-grid cols-3v" style={{ gap: t.space[3] }}>
            <div style={{ padding: `${t.space[2]} ${t.space[3]}`, background: colors.hoverBg, border: `1px solid ${colors.border}`, borderRadius: t.radius.md }}>
              <div style={{ fontSize: t.font.sm, color: colors.textSecondary, marginBottom: t.space[2] }}>技术结论</div>
              <div style={{ fontSize: t.font.md, color: colors.textSecondary, lineHeight: t.leading.relaxed }}>{result.technical.summary}</div>
            </div>
            <div style={{ padding: `${t.space[2]} ${t.space[3]}`, background: colors.hoverBg, border: `1px solid ${colors.border}`, borderRadius: t.radius.md }}>
              <div style={{ fontSize: t.font.sm, color: colors.textSecondary, marginBottom: t.space[2] }}>趋势判断</div>
              <div style={{ fontSize: t.font.xl, fontWeight: Number(t.weight.bold), color: colors.textPrimary }}>{result.technical.trend || "-"}</div>
            </div>
            <div style={{ padding: `${t.space[2]} ${t.space[3]}`, background: colors.hoverBg, border: `1px solid ${colors.border}`, borderRadius: t.radius.md }}>
              <div style={{ fontSize: t.font.sm, color: colors.textSecondary, marginBottom: t.space[2] }}>关键位</div>
              <div style={{ fontSize: t.font.md, color: colors.textSecondary, lineHeight: t.leading.relaxed }}>
                支撑 {result.technical.support_level?.toFixed(2) ?? "-"} / 压力 {result.technical.resistance_level?.toFixed(2) ?? "-"}
              </div>
            </div>
          </div>
        </Card>
      )}
    </>
  );
});
