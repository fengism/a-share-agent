import { Card, Tag, Typography } from "antd";
import { useIndicators } from "../../api/queries";
import type { AnalysisResult, TechnicalIndicators } from "../../types/stock";
import AnalysisDimensionSummary from "./AnalysisDimensionSummary";
import SectionDataState from "../../components/SectionDataState";
import { useColors, useStyles, semanticTagStyle } from "../../theme/hooks";
import type { SemanticTagColor } from "../../theme/hooks";
import "./technical-panel.css";

interface Props {
  code: string;
  analysis?: AnalysisResult | null;
}

const { Paragraph, Text } = Typography;

function getRsiColor(rsi: number | null, colors: { textSecondary: string; up: string; down: string; primary: string }): string {
  if (rsi === null) return colors.textSecondary;
  if (rsi > 70) return colors.up;
  if (rsi < 30) return colors.down;
  return colors.primary;
}

function getMacdSignal(macd: TechnicalIndicators["macd"], colors: { textSecondary: string; up: string; down: string; primary: string }): { text: string; color: string } {
  if (macd.dif === null || macd.dea === null) return { text: "-", color: colors.textSecondary };
  if (macd.dif > macd.dea && macd.macd_hist && macd.macd_hist > 0) return { text: "多头", color: colors.up };
  if (macd.dif < macd.dea && macd.macd_hist && macd.macd_hist < 0) return { text: "空头", color: colors.down };
  return { text: "震荡", color: colors.primary };
}

function Indicator({ label, value, color, styles: tileStyles, colors }: { label: string; value: string; color?: string; styles: { tile: React.CSSProperties; value: React.CSSProperties }; colors: { textSecondary: string; textPrimary: string; hoverBg: string; border: string } }) {
  return (
    <div style={{ ...tileStyles.tile, textAlign: "center" }}>
      <div style={{ color: colors.textSecondary, fontSize: "var(--c-font-sm)", marginBottom: "var(--c-space-1)" }}>{label}</div>
      <div style={{ ...tileStyles.value, color: color || colors.textPrimary, lineHeight: "var(--c-leading-tight)" }}>{value}</div>
    </div>
  );
}

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

export default function TechnicalPanel({ code, analysis }: Props) {
  const c = useColors();
  const { cardStyle, sectionHeaderStyle, tagStyle } = useStyles();
  const { data: indicators, isLoading, error, refetch } = useIndicators(code);

  if (!indicators) {
    return (
      <SectionDataState
        isLoading={isLoading}
        error={error}
        onRetry={() => refetch()}
        isEmpty={!isLoading && !error && !indicators}
        emptyText="暂无技术指标数据"
        errorTitle="技术指标加载失败"
        minHeight={240}
      >
        {null}
      </SectionDataState>
    );
  }

  const { ma, macd, rsi, boll, kdj, volume_ma } = indicators;
  const colorCtx = { textSecondary: c.textSecondary, up: c.up, down: c.down, primary: c.primary };
  const macdSignal = getMacdSignal(macd, colorCtx);
  const tileColors = { textSecondary: c.textSecondary, textPrimary: c.textPrimary, hoverBg: c.hoverBg, border: c.border };
  const tileStyles = {
    tile: { padding: "var(--c-space-3) var(--c-space-4)", background: c.hoverBg, border: `1px solid ${c.border}`, borderRadius: "var(--c-radius-md)" },
    value: { fontSize: "var(--c-font-lg)", fontWeight: 600 },
  };

  return (
    <div style={{ display: "grid", gap: "var(--c-space-4)" }}>
      {analysis?.technical && (
        <Card
          size="small"
          className="analysis-dimension-card"
          style={{ ...cardStyle, borderTop: `3px solid ${c.primary}55` }}
        >
          <AnalysisDimensionSummary label="技术面" score={analysis.technical.score}>
            {analysis.technical.trend && (
              <div className="analysis-dimension-summary__tags">
                <Tag style={{ ...semanticTagStyle("info"), margin: 0, borderRadius: "var(--c-radius-pill)", paddingInline: 10 }}>
                  趋势：{analysis.technical.trend}
                </Tag>
              </div>
            )}
            <Paragraph className="analysis-dimension-summary__description">
              {analysis.technical.summary}
            </Paragraph>
            <div className="technical-summary__signal-list">
              <Text strong style={{ color: c.primary }}>关键信号</Text>
              <div className="analysis-dimension-summary__tags">
                {renderTags(analysis.technical.key_signals, "primary", { ...tagStyle, margin: 0 })}
              </div>
            </div>
            <div className="technical-summary__levels">
              <div className="technical-summary__level">
                <Text type="secondary">支撑位</Text>
                <strong>{analysis.technical.support_level?.toFixed(2) ?? "-"}</strong>
              </div>
              <div className="technical-summary__level">
                <Text type="secondary">压力位</Text>
                <strong>{analysis.technical.resistance_level?.toFixed(2) ?? "-"}</strong>
              </div>
            </div>
          </AnalysisDimensionSummary>
        </Card>
      )}

      <div style={sectionHeaderStyle}>
        <Text strong style={{ color: c.textPrimary, fontSize: "var(--c-font-md)" }}>均线与趋势</Text>
        <Text type="secondary" style={{ fontSize: "var(--c-font-sm)" }}>中短周期趋势判断</Text>
      </div>
      <div className="metric-grid cols-4" style={{ gap: "var(--c-space-3)", marginBottom: "var(--c-space-4)" }}>
        <Indicator label="MA5" value={ma.ma5?.toFixed(2) ?? "-"} colors={tileColors} styles={tileStyles} />
        <Indicator label="MA10" value={ma.ma10?.toFixed(2) ?? "-"} colors={tileColors} styles={tileStyles} />
        <Indicator label="MA20" value={ma.ma20?.toFixed(2) ?? "-"} colors={tileColors} styles={tileStyles} />
        <Indicator label="MA60" value={ma.ma60?.toFixed(2) ?? "-"} colors={tileColors} styles={tileStyles} />
      </div>

      <div style={sectionHeaderStyle}>
        <Text strong style={{ color: c.textPrimary, fontSize: "var(--c-font-md)" }}>动量指标</Text>
        <Text type="secondary" style={{ fontSize: "var(--c-font-sm)" }}>MACD、RSI、KDJ 联合观察</Text>
      </div>
      <div className="metric-grid cols-4" style={{ gap: "var(--c-space-3)", marginBottom: "var(--c-space-4)" }}>
        <Indicator
          label="MACD信号"
          value={macdSignal.text}
          color={macdSignal.color}
          colors={tileColors}
          styles={tileStyles}
        />
        <Indicator
          label="RSI(14)"
          value={rsi?.toFixed(1) ?? "-"}
          color={getRsiColor(rsi, colorCtx)}
          colors={tileColors}
          styles={tileStyles}
        />
        <Indicator
          label="KDJ"
          value={`K:${kdj.k?.toFixed(1) ?? "-"} D:${kdj.d?.toFixed(1) ?? "-"} J:${kdj.j?.toFixed(1) ?? "-"}`}
          colors={tileColors}
          styles={tileStyles}
        />
        <Indicator
          label="DIF/DEA"
          value={`${macd.dif?.toFixed(2) ?? "-"} / ${macd.dea?.toFixed(2) ?? "-"}`}
          colors={tileColors}
          styles={tileStyles}
        />
      </div>

      <div style={sectionHeaderStyle}>
        <Text strong style={{ color: c.textPrimary, fontSize: "var(--c-font-md)" }}>波动区间</Text>
        <Text type="secondary" style={{ fontSize: "var(--c-font-sm)" }}>布林带上下轨观察</Text>
      </div>
      <div className="metric-grid cols-3" style={{ gap: "var(--c-space-3)", marginBottom: "var(--c-space-4)" }}>
        <Indicator label="BOLL上轨" value={boll.upper?.toFixed(2) ?? "-"} colors={tileColors} styles={tileStyles} />
        <Indicator label="BOLL中轨" value={boll.middle?.toFixed(2) ?? "-"} colors={tileColors} styles={tileStyles} />
        <Indicator label="BOLL下轨" value={boll.lower?.toFixed(2) ?? "-"} colors={tileColors} styles={tileStyles} />
      </div>

      <div style={sectionHeaderStyle}>
        <Text strong style={{ color: c.textPrimary, fontSize: "var(--c-font-md)" }}>量能配合</Text>
        <Text type="secondary" style={{ fontSize: "var(--c-font-sm)" }}>短期成交量均线</Text>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "var(--c-space-3)" }}>
        <Indicator label="量能MA5" value={volume_ma.ma5?.toFixed(0) ?? "-"} colors={tileColors} styles={tileStyles} />
        <Indicator label="量能MA10" value={volume_ma.ma10?.toFixed(0) ?? "-"} colors={tileColors} styles={tileStyles} />
      </div>
    </div>
  );
}
