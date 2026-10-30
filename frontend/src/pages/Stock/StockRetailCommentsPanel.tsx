import { Card, Progress, Typography } from "antd";
import { useRetailSentiment } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import type { DesignTokens } from "../../theme/themes";
import { useColors, useStyles, useTokens } from "../../theme/hooks";

const { Paragraph, Text } = Typography;

function Indicator({ label, value, colors, t }: { label: string; value: string; colors: { textSecondary: string; textPrimary: string; hoverBg: string; border: string }; t: DesignTokens }) {
  const tileStyle = {
    padding: `${t.space[3]} ${t.space[4]}`,
    background: colors.hoverBg,
    border: `1px solid ${colors.border}`,
    borderRadius: t.radius.lg,
    textAlign: "center" as const,
  };
  return (
    <div style={tileStyle}>
      <div style={{ color: colors.textSecondary, fontSize: t.font.sm, marginBottom: t.space[2] }}>{label}</div>
      <div style={{ fontSize: t.font.lg, fontWeight: Number(t.weight.semibold), color: colors.textPrimary, lineHeight: t.leading.tight }}>{value}</div>
    </div>
  );
}

export default function StockRetailCommentsPanel({ code }: { code: string }) {
  const query = useRetailSentiment(code);
  const retailSentiment = query.data;
  const c = useColors();
  const t = useTokens();
  const { cardStyle, tagStyle } = useStyles();
  const tileColors = { textSecondary: c.textSecondary, textPrimary: c.textPrimary, hoverBg: c.hoverBg, border: c.border };
  const bullishRatio = retailSentiment?.bullish_ratio;
  const bullishPct = bullishRatio != null ? Math.round(bullishRatio * 100) : null;
  const bearishPct = bullishPct != null ? 100 - bullishPct : null;

  return (
    <SectionDataState
      isLoading={query.isLoading}
      error={query.error}
      onRetry={() => query.refetch()}
      isEmpty={!retailSentiment}
      emptyText="暂无散户讨论样本"
      errorTitle="散户评论加载失败"
      minHeight={260}
    >
      <Card size="small" title={`散户评论（${retailSentiment?.guba_post_count ?? 0}条）`} extra={<Text type="secondary">股吧帖子聚合</Text>} style={{ ...cardStyle, marginBottom: t.space[4] }} styles={{ body: { padding: t.space[4] } }}>
        <div className="metric-grid cols-3" style={{ gap: t.space[3], marginBottom: t.space[3] }}>
          <Indicator label="情绪评分" value={retailSentiment?.score != null ? String(retailSentiment.score) : "-"} colors={tileColors} t={t} />
          <Indicator label="讨论帖数" value={`${retailSentiment?.post_count ?? 0}条`} colors={tileColors} t={t} />
          <Indicator label="看多占比" value={bullishRatio != null ? `${(bullishRatio * 100).toFixed(1)}%` : "-"} colors={tileColors} t={t} />
        </div>
        {bullishPct != null && bearishPct != null ? (
          <div style={{ marginBottom: t.space[4] }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: t.font.xs, marginBottom: 4 }}>
              <span style={{ color: c.up, fontWeight: 600 }}>看多 {bullishPct}%</span>
              <span style={{ color: c.down, fontWeight: 600 }}>看空 {bearishPct}%</span>
            </div>
            <Progress
              percent={bullishPct}
              strokeColor={c.up}
              railColor={c.down}
              showInfo={false}
              size="small"
            />
          </div>
        ) : null}
        <div style={tagStyle}>
          <Text strong style={{ color: c.primary }}>情绪摘要：</Text>
        </div>
        <Paragraph style={{ marginBottom: t.space[3], color: c.textSecondary, lineHeight: t.leading.relaxed }}>
          {retailSentiment?.summary || "暂无散户讨论样本"}
        </Paragraph>
        <div style={tagStyle}>
          <Text strong style={{ color: c.primary }}>样本帖子：</Text>
        </div>
        {retailSentiment?.sample_posts && retailSentiment.sample_posts.length > 0 ? (
          <ul className="stock-information-list">
            {retailSentiment.sample_posts.map((item, index) => (
              <li className="stock-information-list__item" key={`${item.publish_time || "post"}-${index}`}>
                <span className="stock-information-list__title">{item.text}</span>
                <span className="stock-information-list__meta">
                  {[item.author, item.publish_time].filter(Boolean).join(" | ") || "-"}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <div style={{ color: c.textSecondary }}>暂无散户讨论样本</div>
        )}
      </Card>
    </SectionDataState>
  );
}
