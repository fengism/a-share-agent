import { Card, Col, List, Row, Tag, Spin, Typography } from "antd";
import { useCategorizedStockNews, useRetailSentiment, useStockSentiment } from "../../api/queries";
import type { AnalysisResult } from "../../types/stock";
import RatingBadge from "../../components/RatingBadge";
import { useColors, useStyles } from "../../theme/hooks";

interface Props {
  code: string;
  analysis?: AnalysisResult | null;
}

const { Paragraph, Text } = Typography;

function Indicator({ label, value, tag, colors }: { label: string; value: string; tag?: { text: string; color: string }; colors: { textSecondary: string; textPrimary: string; elevatedBg: string; border: string } }) {
  const tileStyle = {
    padding: "14px 16px",
    background: colors.elevatedBg,
    border: `1px solid ${colors.border}`,
    borderRadius: 10,
    textAlign: "center" as const,
  };
  return (
    <div style={tileStyle}>
      <div style={{ color: colors.textSecondary, fontSize: 12, marginBottom: 6 }}>{label}</div>
      {tag ? (
        <Tag color={tag.color} style={{ fontSize: 16, padding: "2px 12px", borderRadius: 4 }}>
          {tag.text}
        </Tag>
      ) : (
        <div style={{ fontSize: 16, fontWeight: 600, color: colors.textPrimary, lineHeight: 1.2 }}>{value}</div>
      )}
    </div>
  );
}

function renderTags(items: string[] | undefined, color: string, tagStyle: React.CSSProperties) {
  if (!items || items.length === 0) {
    return <Text type="secondary">暂无</Text>;
  }

  return items.map((item) => (
    <Tag key={item} color={color} style={tagStyle}>
      {item}
    </Tag>
  ));
}

export default function SentimentPanel({ code, analysis }: Props) {
  const c = useColors();
  const { cardStyle, sectionHeaderStyle, tagStyle } = useStyles();
  const { data: categorizedNews, isLoading: newsLoading } = useCategorizedStockNews(code);
  const { data: sentiment, isLoading: sentLoading } = useStockSentiment(code);
  const { data: retailSentiment, isLoading: retailLoading } = useRetailSentiment(code);

  if (newsLoading || sentLoading || retailLoading) return <Spin />;

  const heatScore = sentiment?.heat_score;
  const hotRank = sentiment?.hot_rank;

  const heatTag = heatScore !== null && heatScore !== undefined
    ? { text: String(heatScore), color: heatScore > 80 ? "red" : heatScore > 50 ? "orange" : "blue" }
    : undefined;

  const tileColors = { textSecondary: c.textSecondary, textPrimary: c.textPrimary, elevatedBg: c.elevatedBg, border: c.border };

  return (
    <div style={{ display: "grid", gap: 16 }}>
      {analysis?.sentiment && (
        <Card
          size="small"
          style={{ ...cardStyle, marginBottom: 16, borderTop: `3px solid ${c.primary}55` }}
          styles={{ body: { padding: 14 } }}
        >
          <Row gutter={[16, 16]} align="middle">
            <Col xs={24} sm={6} style={{ textAlign: "center" }}>
              <RatingBadge score={analysis.sentiment.score} size={64} />
              <div style={{ marginTop: 8, fontWeight: 600, color: c.textPrimary }}>情绪面评分</div>
              {(analysis.sentiment.market_mood || analysis.sentiment.heat_level) && (
                <div style={{ marginTop: 10 }}>
                  {analysis.sentiment.market_mood && (
                    <Tag color="blue" style={{ borderRadius: 999, paddingInline: 10 }}>市场情绪：{analysis.sentiment.market_mood}</Tag>
                  )}
                  {analysis.sentiment.heat_level && (
                    <Tag color="cyan" style={{ borderRadius: 999, paddingInline: 10 }}>热度：{analysis.sentiment.heat_level}</Tag>
                  )}
                </div>
              )}
            </Col>
            <Col xs={24} sm={18}>
              <Paragraph style={{ marginBottom: 12, color: c.textSecondary, lineHeight: 1.8 }}>
                {analysis.sentiment.summary}
              </Paragraph>
              <div style={tagStyle}>
                <Text strong style={{ color: c.primary }}>积极因素：</Text>
              </div>
              <div style={{ marginBottom: 12 }}>
                {renderTags(analysis.sentiment.strengths, "blue", tagStyle)}
              </div>
              <div style={tagStyle}>
                <Text strong style={{ color: c.up }}>情绪风险：</Text>
              </div>
              <div>
                {renderTags(analysis.sentiment.risks, "red", tagStyle)}
              </div>
            </Col>
          </Row>
        </Card>
      )}

      <div style={sectionHeaderStyle}>
        <Text strong style={{ color: c.textPrimary, fontSize: 13 }}>情绪与热度快照</Text>
        <Text type="secondary" style={{ fontSize: 12 }}>市场关注度概览</Text>
      </div>
      <div className="metric-grid cols-3" style={{ gap: 12, marginBottom: 16 }}>
        <Indicator
          label="热度评分"
          value={heatScore != null ? String(heatScore) : "-"}
          tag={heatTag}
          colors={tileColors}
        />
        <Indicator label="热度排名" value={hotRank ? `#${String(hotRank)}` : "-"} colors={tileColors} />
        <Indicator label="相关新闻" value={`${(categorizedNews?.eastmoney_news.length ?? 0) + (categorizedNews?.cls_news.length ?? 0)}条`} colors={tileColors} />
      </div>

      <div style={sectionHeaderStyle}>
        <Text strong style={{ color: c.textPrimary, fontSize: 13 }}>散户讨论</Text>
        <Text type="secondary" style={{ fontSize: 12 }}>股吧情绪样本</Text>
      </div>
      <Card size="small" title={`散户评论情绪（${retailSentiment?.guba_post_count ?? 0}条）`} extra={<Text type="secondary">股吧帖子聚合</Text>} style={{ ...cardStyle, marginBottom: 16 }} styles={{ body: { padding: 14 } }}>
        <div className="metric-grid cols-3" style={{ gap: 12, marginBottom: 16 }}>
          <Indicator label="情绪评分" value={retailSentiment?.score != null ? String(retailSentiment.score) : "-"} colors={tileColors} />
          <Indicator label="讨论帖数" value={`${retailSentiment?.post_count ?? 0}条`} colors={tileColors} />
          <Indicator label="看多占比" value={retailSentiment?.bullish_ratio != null ? `${(retailSentiment.bullish_ratio * 100).toFixed(1)}%` : "-"} colors={tileColors} />
        </div>
        <div style={tagStyle}>
          <Text strong style={{ color: c.primary }}>情绪摘要：</Text>
        </div>
        <Paragraph style={{ marginBottom: 12, color: c.textSecondary, lineHeight: 1.8 }}>
          {retailSentiment?.summary || "暂无散户讨论样本"}
        </Paragraph>
        <div style={tagStyle}>
          <Text strong style={{ color: c.primary }}>样本帖子：</Text>
        </div>
        {retailSentiment?.sample_posts && retailSentiment.sample_posts.length > 0 ? (
          <List
            size="small"
            dataSource={retailSentiment.sample_posts}
            renderItem={(item) => (
              <List.Item style={{ padding: "6px 0" }}>
                <List.Item.Meta
                  title={<span style={{ fontSize: 13, color: c.textSecondary, lineHeight: 1.7 }}>{item.text}</span>}
                  description={
                    <span style={{ fontSize: 12, color: c.textSecondary }}>
                      {[item.author, item.publish_time].filter(Boolean).join(" | ") || "-"}
                    </span>
                  }
                />
              </List.Item>
            )}
          />
        ) : (
          <div style={{ color: c.textSecondary }}>暂无散户讨论样本</div>
        )}
      </Card>

      <div style={sectionHeaderStyle}>
        <Text strong style={{ color: c.textPrimary, fontSize: 13 }}>快讯与资讯</Text>
        <Text type="secondary" style={{ fontSize: 12 }}>新闻流跟踪</Text>
      </div>
      <Card size="small" title={`财联社消息（${categorizedNews?.cls_news.length ?? 0}条）`} extra={<Text type="secondary">更偏快讯信号</Text>} style={{ ...cardStyle, marginBottom: 16 }} styles={{ body: { padding: 14 } }}>
        {categorizedNews?.cls_news && categorizedNews.cls_news.length > 0 ? (
          <List
            size="small"
            dataSource={categorizedNews.cls_news}
            renderItem={(item) => (
              <List.Item style={{ padding: "6px 0" }}>
                <List.Item.Meta
                  title={<span style={{ fontSize: 13, color: c.textPrimary }}>{item.title}</span>}
                  description={<span style={{ fontSize: 12, color: c.textSecondary }}>{item.time}</span>}
                />
              </List.Item>
            )}
          />
        ) : (
          <div style={{ color: c.textSecondary }}>暂无财联社消息</div>
        )}
      </Card>

      <Card size="small" title={`东方财富新闻（${categorizedNews?.eastmoney_news.length ?? 0}条）`} extra={<Text type="secondary">更偏资讯与报道</Text>} style={cardStyle} styles={{ body: { padding: 14 } }}>
        {categorizedNews?.eastmoney_news && categorizedNews.eastmoney_news.length > 0 ? (
          <List
            size="small"
            dataSource={categorizedNews.eastmoney_news}
            renderItem={(item) => (
              <List.Item style={{ padding: "6px 0" }}>
                <List.Item.Meta
                  title={<span style={{ fontSize: 13, color: c.textPrimary }}>{item.title}</span>}
                  description={
                    <span style={{ fontSize: 12, color: c.textSecondary }}>
                      {item.source} | {item.time}
                    </span>
                  }
                />
              </List.Item>
            )}
          />
        ) : (
          <div style={{ color: c.textSecondary }}>暂无东方财富新闻</div>
        )}
      </Card>
    </div>
  );
}
