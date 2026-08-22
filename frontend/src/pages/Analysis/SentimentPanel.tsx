import { Card, Tag, Typography } from "antd";
import { useCategorizedStockNews, useRetailSentiment, useStockSentiment } from "../../api/queries";
import type { AnalysisResult } from "../../types/stock";
import AnalysisDimensionSummary from "./AnalysisDimensionSummary";
import SectionDataState from "../../components/SectionDataState";
import type { DesignTokens } from "../../theme/themes";
import { useColors, useStyles, useTokens, semanticTagStyle } from "../../theme/hooks";
import type { SemanticTagColor } from "../../theme/hooks";

interface Props {
  code: string;
  analysis?: AnalysisResult | null;
}

const { Paragraph, Text } = Typography;

function Indicator({ label, value, tag, colors, t }: { label: string; value: string; tag?: { text: string; color: SemanticTagColor }; colors: { textSecondary: string; textPrimary: string; hoverBg: string; border: string }; t: DesignTokens }) {
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
      {tag ? (
        <Tag style={{ ...semanticTagStyle(tag.color), fontSize: t.font.lg, padding: `2px ${t.space[3]}`, borderRadius: t.radius.sm }}>
          {tag.text}
        </Tag>
      ) : (
        <div style={{ fontSize: t.font.lg, fontWeight: Number(t.weight.semibold), color: colors.textPrimary, lineHeight: t.leading.tight }}>{value}</div>
      )}
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

export default function SentimentPanel({ code, analysis }: Props) {
  const c = useColors();
  const t = useTokens();
  const { cardStyle, sectionHeaderStyle, tagStyle } = useStyles();
  const newsQuery = useCategorizedStockNews(code);
  const sentimentQuery = useStockSentiment(code);
  const retailQuery = useRetailSentiment(code);
  const categorizedNews = newsQuery.data;
  const sentiment = sentimentQuery.data;
  const retailSentiment = retailQuery.data;
  const isLoading = newsQuery.isLoading || sentimentQuery.isLoading || retailQuery.isLoading;
  const error = newsQuery.error || sentimentQuery.error || retailQuery.error;

  const heatScore = sentiment?.heat_score;
  const hotRank = sentiment?.hot_rank;

  const heatTag = heatScore !== null && heatScore !== undefined
    ? { text: String(heatScore), color: (heatScore > 80 ? "up" : heatScore > 50 ? "warning" : "primary") as SemanticTagColor }
    : undefined;

  const tileColors = { textSecondary: c.textSecondary, textPrimary: c.textPrimary, hoverBg: c.hoverBg, border: c.border };

  return (
    <SectionDataState
      isLoading={isLoading}
      error={error}
      onRetry={() => Promise.all([
        newsQuery.refetch(),
        sentimentQuery.refetch(),
        retailQuery.refetch(),
      ])}
      errorTitle="情绪数据加载失败"
      skeletonRows={6}
      minHeight={280}
    >
      <div style={{ display: "grid", gap: t.space[4] }}>
      {analysis?.sentiment && (
        <Card
          size="small"
          className="analysis-dimension-card"
          style={{ ...cardStyle, borderTop: `3px solid ${c.primary}55` }}
        >
          <AnalysisDimensionSummary label="情绪面" score={analysis.sentiment.score}>
            {(analysis.sentiment.market_mood || analysis.sentiment.heat_level) && (
              <div className="analysis-dimension-summary__tags">
                {analysis.sentiment.market_mood && (
                  <Tag style={{ ...semanticTagStyle("info"), margin: 0, borderRadius: t.radius.pill, paddingInline: t.space[3] }}>市场情绪：{analysis.sentiment.market_mood}</Tag>
                )}
                {analysis.sentiment.heat_level && (
                  <Tag style={{ ...semanticTagStyle("accent"), margin: 0, borderRadius: t.radius.pill, paddingInline: t.space[3] }}>热度：{analysis.sentiment.heat_level}</Tag>
                )}
              </div>
            )}
            <Paragraph className="analysis-dimension-summary__description">
              {analysis.sentiment.summary}
            </Paragraph>
            <div className="analysis-dimension-summary__groups">
              <div className="analysis-dimension-summary__group">
                <Text strong style={{ color: c.primary }}>积极因素</Text>
                <div className="analysis-dimension-summary__tags">
                  {renderTags(analysis.sentiment.strengths, "primary", { ...tagStyle, margin: 0 })}
                </div>
              </div>
              <div className="analysis-dimension-summary__group">
                <Text strong style={{ color: c.up }}>情绪风险</Text>
                <div className="analysis-dimension-summary__tags">
                  {renderTags(analysis.sentiment.risks, "up", { ...tagStyle, margin: 0 })}
                </div>
              </div>
            </div>
          </AnalysisDimensionSummary>
        </Card>
      )}

      <div style={sectionHeaderStyle}>
        <Text strong style={{ color: c.textPrimary, fontSize: t.font.md }}>情绪与热度快照</Text>
        <Text type="secondary" style={{ fontSize: t.font.sm }}>市场关注度概览</Text>
      </div>
      <div className="metric-grid cols-3" style={{ gap: t.space[3], marginBottom: t.space[4] }}>
        <Indicator
          label="热度评分"
          value={heatScore != null ? String(heatScore) : "-"}
          tag={heatTag}
          colors={tileColors}
          t={t}
        />
        <Indicator label="热度排名" value={hotRank ? `#${String(hotRank)}` : "-"} colors={tileColors} t={t} />
        <Indicator label="相关新闻" value={`${(categorizedNews?.eastmoney_news.length ?? 0) + (categorizedNews?.cls_news.length ?? 0)}条`} colors={tileColors} t={t} />
      </div>

      <div style={sectionHeaderStyle}>
        <Text strong style={{ color: c.textPrimary, fontSize: t.font.md }}>散户讨论</Text>
        <Text type="secondary" style={{ fontSize: t.font.sm }}>股吧情绪样本</Text>
      </div>
      <Card size="small" title={`散户评论情绪（${retailSentiment?.guba_post_count ?? 0}条）`} extra={<Text type="secondary">股吧帖子聚合</Text>} style={{ ...cardStyle, marginBottom: t.space[4] }} styles={{ body: { padding: t.space[4] } }}>
        <div className="metric-grid cols-3" style={{ gap: t.space[3], marginBottom: t.space[4] }}>
          <Indicator label="情绪评分" value={retailSentiment?.score != null ? String(retailSentiment.score) : "-"} colors={tileColors} t={t} />
          <Indicator label="讨论帖数" value={`${retailSentiment?.post_count ?? 0}条`} colors={tileColors} t={t} />
          <Indicator label="看多占比" value={retailSentiment?.bullish_ratio != null ? `${(retailSentiment.bullish_ratio * 100).toFixed(1)}%` : "-"} colors={tileColors} t={t} />
        </div>
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
          <ul className="analysis-detail-list">
            {retailSentiment.sample_posts.map((item, index) => (
              <li className="analysis-detail-list__item" key={`${item.publish_time || "post"}-${index}`}>
                <span className="analysis-detail-list__title is-secondary">{item.text}</span>
                <span className="analysis-detail-list__meta">
                  {[item.author, item.publish_time].filter(Boolean).join(" | ") || "-"}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <div style={{ color: c.textSecondary }}>暂无散户讨论样本</div>
        )}
      </Card>

      <div style={sectionHeaderStyle}>
        <Text strong style={{ color: c.textPrimary, fontSize: t.font.md }}>快讯与资讯</Text>
        <Text type="secondary" style={{ fontSize: t.font.sm }}>新闻流跟踪</Text>
      </div>
      <Card size="small" title={`财联社消息（${categorizedNews?.cls_news.length ?? 0}条）`} extra={<Text type="secondary">更偏快讯信号</Text>} style={{ ...cardStyle, marginBottom: t.space[4] }} styles={{ body: { padding: t.space[4] } }}>
        {categorizedNews?.cls_news && categorizedNews.cls_news.length > 0 ? (
          <ul className="analysis-detail-list">
            {categorizedNews.cls_news.map((item, index) => (
              <li className="analysis-detail-list__item" key={`${item.publish_time || "cls"}-${index}`}>
                <span className="analysis-detail-list__title">{item.title}</span>
                <span className="analysis-detail-list__meta">{item.publish_time}</span>
              </li>
            ))}
          </ul>
        ) : (
          <div style={{ color: c.textSecondary }}>暂无财联社消息</div>
        )}
      </Card>

      <Card size="small" title={`东方财富新闻（${categorizedNews?.eastmoney_news.length ?? 0}条）`} extra={<Text type="secondary">更偏资讯与报道</Text>} style={cardStyle} styles={{ body: { padding: t.space[4] } }}>
        {categorizedNews?.eastmoney_news && categorizedNews.eastmoney_news.length > 0 ? (
          <ul className="analysis-detail-list">
            {categorizedNews.eastmoney_news.map((item, index) => (
              <li className="analysis-detail-list__item" key={`${item.publish_time || "eastmoney"}-${index}`}>
                <span className="analysis-detail-list__title">{item.title}</span>
                <span className="analysis-detail-list__meta">{item.source} | {item.publish_time}</span>
              </li>
            ))}
          </ul>
        ) : (
          <div style={{ color: c.textSecondary }}>暂无东方财富新闻</div>
        )}
      </Card>
      </div>
    </SectionDataState>
  );
}
