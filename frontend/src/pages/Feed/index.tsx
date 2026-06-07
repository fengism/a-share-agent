import React, { useState, useMemo } from "react";
import { List, Pagination, Tabs, Tag, Typography, Empty, Spin, Tooltip } from "antd";
import { LinkOutlined, RobotOutlined, ThunderboltOutlined, ReadOutlined, ClockCircleOutlined } from "@ant-design/icons";
import type { NewsAnalysisItem, NewsAnalysisRef } from "../../types/stock";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import "dayjs/locale/zh-cn";
import { useMarketKuaixun, useMarketOtherNews, useMarketTwitterFeed, useNewsAnalysis } from "../../api/queries";
import { pageContainerStyle, pageHeaderStyle, pageTitleStyle, pageDescriptionStyle, cardStyle } from "../../styles/ui";
import type { FeedNewsItem } from "../../types/stock";

dayjs.extend(relativeTime);
dayjs.locale("zh-cn");

const { Title, Paragraph, Text } = Typography;

/* ── 配色常量 ──────────────────────────────────────────── */

const KUAIXUN_ACCENT = "#f59e0b";
const KUAIXUN_ACCENT_BG = "rgba(245,158,11,0.08)";

const SOURCE_COLORS: Record<string, string> = {
  "东方财富": "#3b82f6",
  "财联社": "#ef4444",
  "百度": "#60a5fa",
  "华尔街见闻": "#a78bfa",
  "36氪": "#38bdf8",
  "雪球": "#f87171",
  "界面新闻": "#34d399",
  "经济观察报": "#818cf8",
  "Twitter": "#60a5fa",
  "联合早报": "#c084fc",
  "cnnews": "#4ade80",
  "其他": "#64748b",
};

const SENTIMENT_CONFIG: Record<string, { color: string; bg: string }> = {
  "偏多": { color: "#ef4444", bg: "rgba(239,68,68,0.10)" },
  "偏空": { color: "#22c55e", bg: "rgba(34,197,94,0.10)" },
  "中性": { color: "#eab308", bg: "rgba(234,179,8,0.10)" },
};

/* ── 工具函数 ──────────────────────────────────────────── */

function getSourceColor(source: string): string {
  if (source.includes("快讯")) return KUAIXUN_ACCENT;
  for (const [key, color] of Object.entries(SOURCE_COLORS)) {
    if (source.includes(key)) return color;
  }
  return "#64748b";
}

function getSourceLabel(source: string): string {
  if (source.includes("快讯")) return "7×24 快讯";
  if (!source) return "未知";
  for (const key of Object.keys(SOURCE_COLORS)) {
    if (source.includes(key)) return key;
  }
  return source;
}

/* 将原始 source 映射为平台名，用于子 tab 分组 */
const PLATFORM_MAP: Record<string, string> = {
  "东方财富": "东方财富",
  "财联社": "财联社",
  "cnnews": "中国新闻",
  "联合早报": "联合早报",
  "36氪": "36氪",
  "雪球": "雪球",
  "界面新闻": "界面新闻",
  "经济观察报": "经济观察报",
  "华尔街见闻": "华尔街见闻",
  "Twitter": "Twitter",
};

function getSourcePlatform(source: string): string {
  if (source.includes("快讯")) return "7×24 快讯";
  for (const [key, platform] of Object.entries(PLATFORM_MAP)) {
    if (source.includes(key)) return platform;
  }
  return "其他";
}

function formatTime(time: string): string {
  if (!time) return "";
  const d = dayjs(time);
  if (!d.isValid()) return time;
  const diffMin = dayjs().diff(d, "minute");
  if (diffMin < 60) return `${diffMin}分钟前`;
  const diffHour = dayjs().diff(d, "hour");
  if (diffHour < 24) return `${diffHour}小时前`;
  return d.format("MM-DD HH:mm");
}

function getTimeColor(time: string): string {
  const d = dayjs(time);
  if (!d.isValid()) return "#64748b";
  const diffMin = dayjs().diff(d, "minute");
  if (diffMin < 30) return KUAIXUN_ACCENT;
  if (diffMin < 120) return "#94a3b8";
  return "#64748b";
}

/* ── AI 摘要面板 ───────────────────────────────────────── */

/** 单条摘要观点，含引用来源链接 */
function SummaryItem({ item }: { item: NewsAnalysisItem }) {
  const refs: NewsAnalysisRef[] = item.urls || [];
  return (
    <li style={{ marginBottom: 6 }}>
      <Text style={{ color: "#cbd5e1", fontSize: 12.5, lineHeight: 1.8 }}>
        {item.text}
      </Text>
      {refs.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4, marginTop: 2, paddingLeft: 2 }}>
          {refs.map((ref, ri) => (
            <Tooltip key={ri} title={ref.title || ref.url} placement="bottom">
              <a
                href={ref.url}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 3,
                  padding: "1px 6px",
                  borderRadius: 3,
                  background: "rgba(59,130,246,0.08)",
                  border: "1px solid rgba(59,130,246,0.15)",
                  color: "#60a5fa",
                  fontSize: 10.5,
                  lineHeight: "16px",
                  textDecoration: "none",
                  transition: "all 0.15s",
                  maxWidth: 200,
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = "rgba(59,130,246,0.16)";
                  e.currentTarget.style.borderColor = "rgba(59,130,246,0.3)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = "rgba(59,130,246,0.08)";
                  e.currentTarget.style.borderColor = "rgba(59,130,246,0.15)";
                }}
              >
                <LinkOutlined style={{ fontSize: 9, flexShrink: 0 }} />
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {ref.title || "来源"}
                </span>
              </a>
            </Tooltip>
          ))}
        </div>
      )}
    </li>
  );
}

function NewsAnalysisPanel() {
  const { data: analysis, isLoading, isError } = useNewsAnalysis();

  if (isLoading) {
    return (
      <div style={{ ...cardStyle, marginTop: 46, padding: "40px 0", textAlign: "center", position: "sticky", top: 24 }}>
        <Spin size="large" />
        <div style={{ marginTop: 12, color: "#64748b", fontSize: 13 }}>AI 正在分析资讯...</div>
      </div>
    );
  }

  if (isError || !analysis) {
    return (
      <div style={{ ...cardStyle, marginTop: 46, padding: 20, position: "sticky", top: 24 }}>
        <div style={{ color: "#64748b", fontSize: 13, textAlign: "center" }}>AI 分析暂不可用</div>
      </div>
    );
  }

  const sentiment = analysis.market_sentiment || "中性";
  const sConfig = SENTIMENT_CONFIG[sentiment] || SENTIMENT_CONFIG["中性"];

  return (
    <div style={{ ...cardStyle, marginTop: 46, padding: 0, position: "sticky", top: 24 }}>
      {/* Header */}
      <div
        style={{
          padding: "14px 16px",
          background: "linear-gradient(135deg, rgba(59,130,246,0.12), rgba(99,102,241,0.08))",
          borderBottom: "1px solid #1e293b",
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <RobotOutlined style={{ color: "#3b82f6", fontSize: 15 }} />
        <span style={{ color: "#e2e8f0", fontWeight: 600, fontSize: 14 }}>AI 资讯摘要</span>
        <span
          style={{
            marginLeft: "auto",
            padding: "2px 10px",
            borderRadius: 10,
            fontSize: 11,
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
        <Text style={{ color: "#cbd5e1", fontSize: 13, lineHeight: 1.75 }}>
          {analysis.summary}
        </Text>
      </div>

      {/* Sections */}
      <div style={{ maxHeight: "calc(100vh - 240px)", overflowY: "auto" }}>
        {(analysis.sections || []).map((section, idx) => (
          <div
            key={idx}
            style={{
              padding: "12px 16px",
              borderBottom: idx < (analysis.sections?.length ?? 0) - 1 ? "1px solid #1e293b" : "none",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
              <span style={{ fontSize: 13 }}>{section.icon}</span>
              <Text style={{ color: "#94a3b8", fontWeight: 600, fontSize: 12, letterSpacing: 0.3 }}>{section.title}</Text>
            </div>
            <ul style={{ margin: 0, paddingLeft: 16, listStyle: "none" }}>
              {(section.items || []).map((item, i) => (
                <SummaryItem key={i} item={item} />
              ))}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── 新闻列表项 ────────────────────────────────────────── */

function NewsListItem({ item, showSourceTag = true }: { item: FeedNewsItem; showSourceTag?: boolean }) {
  const isKuaixun = item.source.includes("快讯");
  return (
    <List.Item
      style={{
        padding: isKuaixun ? "12px 16px 12px 20px" : "14px 16px",
        borderLeft: isKuaixun ? `3px solid ${KUAIXUN_ACCENT}` : "3px solid transparent",
        borderBottom: "1px solid rgba(30,41,59,0.6)",
        transition: "background 0.15s",
        background: isKuaixun ? KUAIXUN_ACCENT_BG : "transparent",
      }}
      onMouseEnter={(e) => { e.currentTarget.style.background = "#1a2332"; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = isKuaixun ? KUAIXUN_ACCENT_BG : "transparent"; }}
    >
      <div style={{ width: "100%" }}>
        {/* Row 1: tag + time + author */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
          {showSourceTag && (
            <Tag
              color={getSourceColor(item.source)}
              style={{
                margin: 0,
                borderRadius: 4,
                fontSize: 11,
                lineHeight: "18px",
                paddingInline: 6,
              }}
            >
              {getSourceLabel(item.source)}
            </Tag>
          )}
          <ClockCircleOutlined style={{ color: "#475569", fontSize: 11 }} />
          <Text style={{ color: getTimeColor(item.publish_time), fontSize: 12 }}>
            {formatTime(item.publish_time)}
          </Text>
          {item.author != null && item.author !== "" && (
            <Tag
              style={{
                margin: 0,
                borderRadius: 4,
                fontSize: 10,
                lineHeight: "16px",
                paddingInline: 5,
                color: "#94a3b8",
                background: "rgba(148,163,184,0.1)",
                border: "1px solid rgba(148,163,184,0.15)",
              }}
            >
              {item.author}
            </Tag>
          )}
        </div>

        {/* Row 2: title */}
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
                  color: isKuaixun ? "#f1f5f9" : "#e2e8f0",
                  fontSize: isKuaixun ? 14 : 14.5,
                  flex: 1,
                  lineHeight: 1.6,
                }}
              >
                {item.title}
              </Text>
              <LinkOutlined style={{ color: "#475569", fontSize: 11, flexShrink: 0, marginLeft: 4 }} />
            </div>
          </a>
        ) : (
          <Text
            strong
            style={{ color: isKuaixun ? "#f1f5f9" : "#e2e8f0", fontSize: isKuaixun ? 14 : 14.5, lineHeight: 1.6 }}
          >
            {item.title}
          </Text>
        )}

        {/* Row 3: content preview */}
        {item.content && (
          <Paragraph
            style={{
              color: "#94a3b8",
              fontSize: 12.5,
              marginTop: 4,
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

        {/* Row 4: engagement */}
        {(item.read_count > 0 || item.comment_count > 0) && (
          <div style={{ marginTop: 4, display: "flex", gap: 12 }}>
            {item.read_count > 0 && (
              <Text style={{ color: "#475569", fontSize: 11 }}>
                阅读 {item.read_count.toLocaleString()}
              </Text>
            )}
            {item.comment_count > 0 && (
              <Text style={{ color: "#475569", fontSize: 11 }}>
                评论 {item.comment_count.toLocaleString()}
              </Text>
            )}
          </div>
        )}
      </div>
    </List.Item>
  );
}

/* ── 带分页的列表容器 ──────────────────────────────────── */

const KUAIXUN_PAGE_SIZE = 30;
const NEWS_PAGE_SIZE = 20;

function PaginatedList({
  items,
  isLoading,
  emptyText,
  showSourceTag,
  pageSize,
}: {
  items: FeedNewsItem[];
  isLoading: boolean;
  emptyText: string;
  showSourceTag: boolean;
  pageSize: number;
}) {
  const [page, setPage] = useState(1);
  const total = items.length;
  const totalPages = Math.ceil(total / pageSize);
  const start = (page - 1) * pageSize;
  const pageItems = items.slice(start, start + pageSize);

  if (isLoading) {
    return (
      <div style={{ ...cardStyle, padding: "60px 0", textAlign: "center" }}>
        <Spin size="large" />
      </div>
    );
  }

  if (total === 0) {
    return <Empty description={emptyText} style={{ padding: "60px 0" }} />;
  }

  return (
    <div style={cardStyle}>
      <List
        dataSource={pageItems}
        renderItem={(item) => <NewsListItem item={item} showSourceTag={showSourceTag} />}
      />
      {totalPages > 1 && (
        <div style={{ padding: "12px 16px", display: "flex", justifyContent: "center", borderTop: "1px solid #1e293b" }}>
          <Pagination
            current={page}
            total={total}
            pageSize={pageSize}
            onChange={setPage}
            size="small"
            showSizeChanger={false}
            showTotal={(t) => `共 ${t} 条`}
          />
        </div>
      )}
    </div>
  );
}

/* ── Tab 内容 ──────────────────────────────────────────── */

function KuaixunTab() {
  const { data: items = [], isLoading } = useMarketKuaixun();
  return (
    <PaginatedList
      items={items}
      isLoading={isLoading}
      emptyText="暂无快讯"
      showSourceTag={false}
      pageSize={KUAIXUN_PAGE_SIZE}
    />
  );
}

function TwitterTab() {
  const { data: items = [], isLoading } = useMarketTwitterFeed();
  return (
    <PaginatedList
      items={items}
      isLoading={isLoading}
      emptyText="暂无 Twitter 资讯"
      showSourceTag={true}
      pageSize={NEWS_PAGE_SIZE}
    />
  );
}

function OtherNewsTab() {
  const { data: items = [], isLoading } = useMarketOtherNews();

  /* 按平台分组 */
  const grouped = useMemo(() => {
    const map = new Map<string, FeedNewsItem[]>();
    for (const item of items) {
      const platform = getSourcePlatform(item.source);
      const arr = map.get(platform);
      if (arr) arr.push(item);
      else map.set(platform, [item]);
    }
    return Array.from(map.entries()).sort((a, b) => b[1].length - a[1].length);
  }, [items]);

  const subTabs = useMemo(() => {
    const tabs: { key: string; label: React.ReactNode; children: React.ReactNode }[] = [
      {
        key: "all",
        label: <span>全部 <Tag style={{ margin: 0, borderRadius: 8, fontSize: 11, lineHeight: "16px", paddingInline: 5 }}>{items.length}</Tag></span>,
        children: (
          <PaginatedList
            items={items}
            isLoading={isLoading}
            emptyText="暂无新闻"
            showSourceTag={true}
            pageSize={NEWS_PAGE_SIZE}
          />
        ),
      },
    ];
    for (const [source, sourceItems] of grouped) {
      tabs.push({
        key: source,
        label: (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: getSourceColor(source),
                flexShrink: 0,
              }}
            />
            {source}
            <Tag style={{ margin: 0, borderRadius: 8, fontSize: 11, lineHeight: "16px", paddingInline: 5 }}>{sourceItems.length}</Tag>
          </span>
        ),
        children: (
          <PaginatedList
            items={sourceItems}
            isLoading={isLoading}
            emptyText={`暂无${source}新闻`}
            showSourceTag={false}
            pageSize={NEWS_PAGE_SIZE}
          />
        ),
      });
    }
    return tabs;
  }, [grouped, items, isLoading]);

  if (isLoading) {
    return (
      <div style={{ ...cardStyle, padding: "60px 0", textAlign: "center" }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <Tabs
      defaultActiveKey="all"
      tabPosition="top"
      size="small"
      items={subTabs}
      style={{ background: "transparent" }}
    />
  );
}

/* ── 主页面 ────────────────────────────────────────────── */

export default function Feed() {
  return (
    <div style={pageContainerStyle}>
      <div style={pageHeaderStyle}>
        <Title level={3} style={pageTitleStyle}>24小时资讯</Title>
        <Paragraph style={pageDescriptionStyle}>
          实时聚合多源市场新闻，AI 智能提炼关键信息
        </Paragraph>
      </div>

      {/* Two-column layout: tabs left, AI analysis right */}
      <div style={{ display: "flex", gap: 16, alignItems: "flex-start" }}>
        {/* Left: Tabs */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <Tabs
            defaultActiveKey="kuaixun"
            size="large"
            items={[
              {
                key: "kuaixun",
                label: <span><ThunderboltOutlined /> 7×24 快讯</span>,
                children: <KuaixunTab />,
              },
              {
                key: "news",
                label: <span><ReadOutlined /> 新闻资讯</span>,
                children: <OtherNewsTab />,
              },
              {
                key: "twitter",
                label: <span>𝕏 Twitter</span>,
                children: <TwitterTab />,
              },
            ]}
            style={{ background: "transparent" }}
          />
        </div>

        {/* Right: AI Analysis */}
        <div style={{ width: 340, flexShrink: 0 }}>
          <NewsAnalysisPanel />
        </div>
      </div>
    </div>
  );
}
