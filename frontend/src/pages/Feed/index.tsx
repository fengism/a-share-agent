import { useState } from "react";
import { List, Segmented, Tag, Typography, Empty, Spin } from "antd";
import { LinkOutlined, RobotOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import "dayjs/locale/zh-cn";
import { useMarketFeed, useNewsAnalysis } from "../../api/queries";
import { pageContainerStyle, pageHeaderStyle, pageTitleStyle, pageDescriptionStyle, cardStyle } from "../../styles/ui";
import type { FeedNewsItem } from "../../types/stock";

dayjs.extend(relativeTime);
dayjs.locale("zh-cn");

const { Title, Paragraph, Text } = Typography;

const SOURCE_OPTIONS = [
  { label: "全部", value: "all" },
  { label: "东方财富", value: "东方财富" },
  { label: "财联社", value: "财联社" },
  { label: "7x24快讯", value: "东方财富快讯" },
  { label: "百度", value: "百度" },
  { label: "36氪", value: "36氪" },
  { label: "雪球", value: "雪球" },
  { label: "界面", value: "界面新闻" },
  { label: "经观", value: "经济观察报" },
  { label: "联合早报", value: "联合早报" },
  { label: "中国新闻", value: "cnnews" },
];

const SOURCE_COLORS: Record<string, string> = {
  "东方财富": "#3b82f6",
  "财联社": "#ef4444",
  "东方财富快讯": "#f59e0b",
  "百度": "#2563eb",
  "36氪": "#0084ff",
  "雪球": "#e84545",
  "界面新闻": "#00b894",
  "经济观察报": "#6c5ce7",
  "联合早报": "#8b5cf6",
  "cnnews": "#22c55e",
};

const SENTIMENT_CONFIG: Record<string, { color: string; bg: string }> = {
  "偏多": { color: "#ef4444", bg: "rgba(239,68,68,0.12)" },
  "偏空": { color: "#22c55e", bg: "rgba(34,197,94,0.12)" },
  "中性": { color: "#eab308", bg: "rgba(234,179,8,0.12)" },
};

function getSourceColor(source: string): string {
  for (const [key, color] of Object.entries(SOURCE_COLORS)) {
    if (source.includes(key)) return color;
  }
  return "#9ca3af";
}

function getSourceLabel(source: string): string {
  if (!source) return "未知";
  if (source.includes("快讯")) return "7x24快讯";
  for (const key of Object.keys(SOURCE_COLORS)) {
    if (source.includes(key)) return key;
  }
  return source;
}

function filterBySource(items: FeedNewsItem[], source: string): FeedNewsItem[] {
  if (source === "all") return items;
  if (source === "东方财富") {
    return items.filter((item) => item.source.includes("东方财富") && !item.source.includes("快讯"));
  }
  return items.filter((item) => item.source.includes(source));
}

function formatTime(time: string): string {
  if (!time) return "";
  const d = dayjs(time);
  if (!d.isValid()) return time;
  const diffMin = dayjs().diff(d, "minute");
  if (diffMin < 60) return d.fromNow();
  const diffHour = dayjs().diff(d, "hour");
  if (diffHour < 24) return d.fromNow();
  return d.format("MM-DD HH:mm");
}

function NewsAnalysisPanel() {
  const { data: analysis, isLoading, isError } = useNewsAnalysis();

  if (isLoading) {
    return (
      <div style={{ ...cardStyle, padding: "40px 0", textAlign: "center", position: "sticky", top: 24 }}>
        <Spin size="large" />
        <div style={{ marginTop: 12, color: "#6b7280", fontSize: 13 }}>AI 正在分析资讯...</div>
      </div>
    );
  }

  if (isError || !analysis) {
    return (
      <div style={{ ...cardStyle, padding: 20, position: "sticky", top: 24 }}>
        <div style={{ color: "#6b7280", fontSize: 13, textAlign: "center" }}>AI 分析暂不可用</div>
      </div>
    );
  }

  const sentiment = analysis.market_sentiment || "中性";
  const sConfig = SENTIMENT_CONFIG[sentiment] || SENTIMENT_CONFIG["中性"];

  return (
    <div style={{ ...cardStyle, padding: 0, position: "sticky", top: 24 }}>
      {/* Header */}
      <div style={{ padding: "16px 16px 12px", borderBottom: "1px solid #1e293b", display: "flex", alignItems: "center", gap: 8 }}>
        <RobotOutlined style={{ color: "#3b82f6", fontSize: 16 }} />
        <span style={{ color: "#e5e7eb", fontWeight: 600, fontSize: 15 }}>AI 资讯摘要</span>
        <span
          style={{
            marginLeft: "auto",
            padding: "2px 10px",
            borderRadius: 12,
            fontSize: 12,
            fontWeight: 600,
            color: sConfig.color,
            background: sConfig.bg,
          }}
        >
          {sentiment}
        </span>
      </div>

      {/* Summary */}
      <div style={{ padding: "12px 16px", borderBottom: "1px solid #1e293b" }}>
        <Text style={{ color: "#d1d5db", fontSize: 13, lineHeight: 1.7 }}>
          {analysis.summary}
        </Text>
      </div>

      {/* Sections */}
      <div style={{ maxHeight: "calc(100vh - 260px)", overflowY: "auto" }}>
        {(analysis.sections || []).map((section, idx) => (
          <div
            key={idx}
            style={{
              padding: "12px 16px",
              borderBottom: idx < analysis.sections.length - 1 ? "1px solid #1e293b" : "none",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
              <span style={{ fontSize: 14 }}>{section.icon}</span>
              <Text style={{ color: "#9ca3af", fontWeight: 600, fontSize: 13 }}>{section.title}</Text>
            </div>
            <ul style={{ margin: 0, paddingLeft: 16 }}>
              {(section.items || []).map((item, i) => (
                <li key={i}>
                  <Text style={{ color: "#d1d5db", fontSize: 13, lineHeight: 1.8 }}>{item}</Text>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Feed() {
  const { data: feedItems = [], isLoading } = useMarketFeed();
  const [source, setSource] = useState("all");
  const filtered = filterBySource(feedItems, source);

  return (
    <div style={pageContainerStyle}>
      <div style={pageHeaderStyle}>
        <Title level={3} style={pageTitleStyle}>24小时资讯</Title>
        <Paragraph style={pageDescriptionStyle}>
          实时聚合多源市场新闻，AI 智能提炼关键信息
        </Paragraph>
      </div>

      {/* Two-column layout */}
      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        {/* Left: AI Analysis */}
        <div style={{ width: 340, flexShrink: 0 }}>
          <NewsAnalysisPanel />
        </div>

        {/* Right: News List */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ ...cardStyle, padding: "12px 16px", marginBottom: 16 }}>
            <Segmented
              options={SOURCE_OPTIONS}
              value={source}
              onChange={(val) => setSource(val as string)}
            />
            <Text style={{ marginLeft: 12, color: "#6b7280", fontSize: 13 }}>
              共 {filtered.length} 条
            </Text>
          </div>

          <div style={cardStyle}>
            {isLoading ? (
              <div style={{ padding: "60px 0", textAlign: "center" }}>
                <Spin size="large" />
              </div>
            ) : filtered.length === 0 ? (
              <Empty description="暂无近期新闻" style={{ padding: "60px 0" }} />
            ) : (
              <List
                dataSource={filtered}
                renderItem={(item) => (
                  <List.Item
                    style={{
                      padding: "16px 20px",
                      borderBottom: "1px solid #1e293b",
                      transition: "background 0.15s",
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = "#1a2332"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                  >
                    <div style={{ width: "100%" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                        <Tag
                          color={getSourceColor(item.source)}
                          style={{ margin: 0, borderRadius: 4, fontSize: 12, lineHeight: "20px" }}
                        >
                          {getSourceLabel(item.source)}
                        </Tag>
                        <Text style={{ color: "#6b7280", fontSize: 12 }}>
                          {formatTime(item.publish_time)}
                        </Text>
                        {item.author && item.author !== item.source && (
                          <Text style={{ color: "#4b5563", fontSize: 12 }}>
                            {item.author}
                          </Text>
                        )}
                      </div>

                      {item.url ? (
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ textDecoration: "none" }}
                        >
                          <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                            <Text
                              strong
                              style={{
                                color: "#e5e7eb",
                                fontSize: 15,
                                flex: 1,
                              }}
                            >
                              {item.title}
                            </Text>
                            <LinkOutlined style={{ color: "#4b5563", fontSize: 12, flexShrink: 0 }} />
                          </div>
                        </a>
                      ) : (
                        <Text strong style={{ color: "#e5e7eb", fontSize: 15 }}>
                          {item.title}
                        </Text>
                      )}

                      {item.content && (
                        <Paragraph
                          style={{
                            color: "#9ca3af",
                            fontSize: 13,
                            marginTop: 6,
                            marginBottom: 0,
                            lineHeight: 1.6,
                            display: "-webkit-box",
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: "vertical",
                            overflow: "hidden",
                          }}
                        >
                          {item.content}
                        </Paragraph>
                      )}

                      {(item.read_count > 0 || item.comment_count > 0) && (
                        <div style={{ marginTop: 6, display: "flex", gap: 12 }}>
                          {item.read_count > 0 && (
                            <Text style={{ color: "#6b7280", fontSize: 12 }}>
                              阅读 {item.read_count.toLocaleString()}
                            </Text>
                          )}
                          {item.comment_count > 0 && (
                            <Text style={{ color: "#6b7280", fontSize: 12 }}>
                              评论 {item.comment_count.toLocaleString()}
                            </Text>
                          )}
                        </div>
                      )}
                    </div>
                  </List.Item>
                )}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
