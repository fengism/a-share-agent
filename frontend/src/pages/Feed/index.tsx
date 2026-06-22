import React, { useState, useMemo, useEffect } from "react";
import { Button, Input, List, Pagination, Select, Tabs, Tag, Typography, Empty, Skeleton, Tooltip, message } from "antd";
import { LinkOutlined, RobotOutlined, SyncOutlined, ThunderboltOutlined, ReadOutlined, ClockCircleOutlined } from "@ant-design/icons";
import type { NewsAnalysisItem, NewsAnalysisRef } from "../../types/stock";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import "dayjs/locale/zh-cn";
import { useMarketKuaixun, useMarketOtherNews, useMarketTwitterFeed, useMarketTwitterFeedRefresh, useNewsAnalysis } from "../../api/queries";
import { useColors, useStyles } from "../../styles/ui";
import type { FeedNewsItem } from "../../types/stock";
import type { ThemeColors } from "../../theme/themes";

dayjs.extend(relativeTime);
dayjs.locale("zh-cn");

/* ── 响应式 Hook ────────────────────────────────────────── */

function useMediaQuery(query: string): boolean {
  const [matches, setMatches] = React.useState(
    () => typeof window !== "undefined" && window.matchMedia(query).matches,
  );
  React.useEffect(() => {
    const mql = window.matchMedia(query);
    const handler = (e: MediaQueryListEvent) => setMatches(e.matches);
    mql.addEventListener("change", handler);
    setMatches(mql.matches);
    return () => mql.removeEventListener("change", handler);
  }, [query]);
  return matches;
}

const { Title, Paragraph, Text } = Typography;

/* ── 配色常量 ──────────────────────────────────────────── */

const KUAIXUN_ACCENT = "#f59e0b";
const KUAIXUN_ACCENT_BG = "rgba(245,158,11,0.08)";

function getSourceColors(c: ThemeColors): Record<string, string> {
  return {
    "东方财富": c.primary,
    "财联社": c.up,
    "百度": c.primary,
    "华尔街见闻": "#a78bfa",
    "36氪": "#38bdf8",
    "雪球": "#f87171",
    "界面新闻": "#34d399",
    "经济观察报": "#818cf8",
    "Twitter": c.primary,
    "联合早报": "#c084fc",
    "cnnews": "#4ade80",
    "其他": c.textMuted,
  };
}

function getSentimentConfig(c: ThemeColors): Record<string, { color: string; bg: string }> {
  return {
    "偏多": { color: c.up, bg: `${c.up}1a` },
    "偏空": { color: c.down, bg: `${c.down}1a` },
    "中性": { color: c.accent, bg: `${c.accent}1a` },
  };
}

/* ── 工具函数 ──────────────────────────────────────────── */

function getSourceColor(source: string, c: ThemeColors): string {
  if (source.includes("快讯")) return KUAIXUN_ACCENT;
  for (const [key, color] of Object.entries(getSourceColors(c))) {
    if (source.includes(key)) return color;
  }
  return c.textMuted;
}

function isTwitterItem(item: FeedNewsItem): boolean {
  return item.source === "Twitter" || item.source.includes("𝕏");
}

function getSourceLabel(source: string, c: ThemeColors): string {
  if (source.includes("快讯")) return "7×24 快讯";
  if (!source) return "未知";
  for (const key of Object.keys(getSourceColors(c))) {
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

function getTimeColor(time: string, c: ThemeColors): string {
  const d = dayjs(time);
  if (!d.isValid()) return c.textMuted;
  const diffMin = dayjs().diff(d, "minute");
  if (diffMin < 30) return KUAIXUN_ACCENT;
  if (diffMin < 120) return c.textSecondary;
  return "#64748b";
}

/* ── 时间展示（相对时间 + 绝对时间 Tooltip） ────────────── */

function TimeDisplay({ time }: { time: string }) {
  const c = useColors();
  if (!time) return null;
  const d = dayjs(time);
  if (!d.isValid()) return <Text style={{ color: c.textMuted, fontSize: 12 }}>{time}</Text>;
  const absoluteTime = d.format("YYYY-MM-DD HH:mm:ss");
  return (
    <Tooltip title={absoluteTime}>
      <Text style={{ color: getTimeColor(time, c), fontSize: 12 }}>
        {formatTime(time)}
      </Text>
    </Tooltip>
  );
}

/* ── 媒体缩略图 ────────────────────────────────────────── */

function MediaPreview({ imageUrl, title }: { imageUrl: string; title: string }) {
  if (!imageUrl) return null;
  return (
    <div
      style={{
        marginTop: 8,
        borderRadius: 8,
        overflow: "hidden",
        maxWidth: 480,
        border: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      <img
        src={imageUrl}
        alt={title}
        style={{
          width: "100%",
          height: "auto",
          maxHeight: 300,
          objectFit: "cover",
          display: "block",
        }}
        loading="lazy"
      />
    </div>
  );
}

/* ── AI 摘要面板 ───────────────────────────────────────── */

/** 单条摘要观点，含引用来源链接 */
function SummaryItem({ item }: { item: NewsAnalysisItem }) {
  const c = useColors();
  const refs: NewsAnalysisRef[] = item.urls || [];
  return (
    <li style={{ marginBottom: 6 }}>
      <Text style={{ color: c.textPrimary, fontSize: 12.5, lineHeight: 1.8 }}>
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
                  background: `${c.primary}14`,
                  border: "1px solid rgba(59,130,246,0.15)",
                  color: c.primary,
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
                  e.currentTarget.style.background = `${c.primary}14`;
                  e.currentTarget.style.borderColor = `${c.primary}26`;
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
  const c = useColors();
  const { cardStyle } = useStyles();
  const { data: analysis, isLoading, isError } = useNewsAnalysis();

  if (isLoading) {
    return (
      <div style={{ ...cardStyle, padding: 0, marginTop: 46, position: "sticky", top: 24 }}>
        <div style={{ padding: "14px 16px", borderBottom: `1px solid ${c.border}` }}>
          <Skeleton active title={{ width: 120 }} paragraph={false} />
        </div>
        <div style={{ padding: "12px 16px" }}>
          <Skeleton active paragraph={{ rows: 4 }} />
        </div>
      </div>
    );
  }

  if (isError || !analysis) {
    return (
      <div style={{ ...cardStyle, marginTop: 46, padding: 20, position: "sticky", top: 24 }}>
        <div style={{ color: c.textMuted, fontSize: 13, textAlign: "center" }}>AI 分析暂不可用</div>
      </div>
    );
  }

  const sentiment = analysis.market_sentiment || "中性";
  const sConfig = getSentimentConfig(c)[sentiment] || getSentimentConfig(c)["中性"];

  return (
    <div style={{ ...cardStyle, marginTop: 46, padding: 0, position: "sticky", top: 24 }}>
      {/* Header */}
      <div
        style={{
          padding: "14px 16px",
          background: "linear-gradient(135deg, rgba(59,130,246,0.12), rgba(99,102,241,0.08))",
          borderBottom: `1px solid ${c.border}`,
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <RobotOutlined style={{ color: c.primary, fontSize: 15 }} />
        <span style={{ color: c.textPrimary, fontWeight: 600, fontSize: 14 }}>AI 资讯摘要</span>
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
      <div style={{ padding: "12px 16px", borderBottom: `1px solid ${c.border}` }}>
        <Text style={{ color: c.textPrimary, fontSize: 13, lineHeight: 1.75 }}>
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
              borderBottom: idx < (analysis.sections?.length ?? 0) - 1 ? `1px solid ${c.border}` : "none",
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
              <span style={{ fontSize: 13 }}>{section.icon}</span>
              <Text style={{ color: c.textSecondary, fontWeight: 600, fontSize: 12, letterSpacing: 0.3 }}>{section.title}</Text>
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
  const c = useColors();
  const isKuaixun = item.source.includes("快讯");
  return (
    <List.Item
      style={{
        padding: isKuaixun ? "12px 16px 12px 20px" : "14px 16px",
        borderLeft: isKuaixun ? `3px solid ${KUAIXUN_ACCENT}` : "3px solid transparent",
        borderBottom: `1px solid ${c.border}80`,
        transition: "background 0.15s",
        background: isKuaixun ? KUAIXUN_ACCENT_BG : "transparent",
      }}
      onMouseEnter={(e) => { e.currentTarget.style.background = c.elevatedBg; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = isKuaixun ? KUAIXUN_ACCENT_BG : "transparent"; }}
    >
      <div style={{ width: "100%" }}>
        {/* Row 1: tag + time + author */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
          {showSourceTag && (
            <Tag
              color={getSourceColor(item.source, c)}
              style={{
                margin: 0,
                borderRadius: 4,
                fontSize: 11,
                lineHeight: "18px",
                paddingInline: 6,
              }}
            >
              {isTwitterItem(item) ? <span>𝕏 {getSourceLabel(item.source, c)}</span> : getSourceLabel(item.source, c)}
            </Tag>
          )}
          <ClockCircleOutlined style={{ color: c.textMuted, fontSize: 11 }} />
          <TimeDisplay time={item.publish_time} />
          {item.author != null && item.author !== "" && (
            <Tag
              style={{
                margin: 0,
                borderRadius: 4,
                fontSize: 10,
                lineHeight: "16px",
                paddingInline: 5,
                color: c.textSecondary,
                background: `${c.primary}0a`,
                border: `1px solid ${c.border}`,
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
                  color: c.textPrimary,
                  fontSize: isKuaixun ? 14 : 14.5,
                  flex: 1,
                  lineHeight: 1.6,
                }}
              >
                {item.title}
              </Text>
              <LinkOutlined style={{ color: c.textMuted, fontSize: 11, flexShrink: 0, marginLeft: 4 }} />
            </div>
          </a>
        ) : (
          <Text
            strong
            style={{ color: c.textPrimary, fontSize: isKuaixun ? 14 : 14.5, lineHeight: 1.6 }}
          >
            {item.title}
          </Text>
        )}

        {/* Row 3: content preview */}
        {item.content && (
          <Paragraph
            style={{
              color: c.textSecondary,
              fontSize: 12.5,
              marginTop: 4,
              marginBottom: 0,
              lineHeight: 1.6,
              display: "-webkit-box",
              WebkitLineClamp: isTwitterItem(item) ? 5 : 2,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}
          >
            {item.content}
          </Paragraph>
        )}

        {item.image_url && <MediaPreview imageUrl={item.image_url} title={item.title} />}

        {/* Row 4: engagement */}
        {(item.read_count > 0 || item.comment_count > 0) && (
          <div style={{ marginTop: 4, display: "flex", gap: 12 }}>
            {item.read_count > 0 && (
              <Text style={{ color: c.textMuted, fontSize: 11 }}>
                {isTwitterItem(item) ? '浏览' : '阅读'} {item.read_count.toLocaleString()}
              </Text>
            )}
            {item.comment_count > 0 && (
              <Text style={{ color: c.textMuted, fontSize: 11 }}>
                {isTwitterItem(item) ? '回复' : '评论'} {item.comment_count.toLocaleString()}
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
  searchQuery = "",
}: {
  items: FeedNewsItem[];
  isLoading: boolean;
  emptyText: string;
  showSourceTag: boolean;
  pageSize: number;
  searchQuery?: string;
}) {
  const c = useColors();
  const { cardStyle } = useStyles();
  const [page, setPage] = useState(1);

  // Search filter
  const filtered = useMemo(() => {
    if (!searchQuery) return items;
    const q = searchQuery.toLowerCase();
    return items.filter(item =>
      (item.title && item.title.toLowerCase().includes(q)) ||
      (item.content && item.content.toLowerCase().includes(q))
    );
  }, [items, searchQuery]);

  const total = filtered.length;
  const totalPages = Math.ceil(total / pageSize);
  const start = (page - 1) * pageSize;
  const pageItems = filtered.slice(start, start + pageSize);

  if (isLoading) {
    return (
      <div style={{ ...cardStyle, padding: "16px" }}>
        <Skeleton active paragraph={{ rows: 5 }} />
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
        <div style={{ padding: "12px 16px", display: "flex", justifyContent: "center", borderTop: `1px solid ${c.border}` }}>
          <Pagination
            current={page}
            total={total}
            pageSize={pageSize}
            onChange={(p) => { window.scrollTo({ top: 0, behavior: "smooth" }); setPage(p); }}
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

function KuaixunTab({ searchQuery = "" }: { searchQuery?: string }) {
  const c = useColors();
  const { data: items = [], isLoading } = useMarketKuaixun();
  return (
    <div>
      {!isLoading && items.length > 0 && (
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8 }}>
          <Text style={{ color: c.textSecondary, fontSize: 12 }}>
            共 {items.length} 条快讯
          </Text>
        </div>
      )}
      <PaginatedList
        items={items}
        isLoading={isLoading}
        emptyText="暂无快讯"
        showSourceTag={false}
        pageSize={KUAIXUN_PAGE_SIZE}
        searchQuery={searchQuery}
      />
    </div>
  );
}

function TwitterTab({ searchQuery = "" }: { searchQuery?: string }) {
  const c = useColors();
  const { data: items = [], isLoading } = useMarketTwitterFeed();
  const refreshMutation = useMarketTwitterFeedRefresh();
  const [lastRefreshed, setLastRefreshed] = useState<string | null>(null);
  const [, setTick] = useState(0);

  useEffect(() => {
    if (!isLoading && items.length > 0 && !lastRefreshed) {
      setLastRefreshed(new Date().toISOString());
    }
  }, [isLoading, items, lastRefreshed]);

  // Countdown tick every 15s
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 15000);
    return () => clearInterval(id);
  }, []);

  const handleRefresh = () => {
    refreshMutation.mutate(undefined, {
      onSuccess: () => {
        setLastRefreshed(new Date().toISOString());
        message.success("Twitter 资讯已刷新");
      },
      onError: (err) => message.error(err?.message || "刷新失败"),
    });
  };

  const timeSince = lastRefreshed ? dayjs(lastRefreshed).fromNow() : null;

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        {timeSince && (
          <Text style={{ color: c.textSecondary, fontSize: 12 }}>
            <ClockCircleOutlined style={{ marginRight: 4 }} />
            上次更新 {timeSince}
            {items.length > 0 && (
              <span style={{ marginLeft: 8 }}>· 共 {items.length} 条</span>
            )}
          </Text>
        )}
        <div style={{ flex: 1 }} />
        <Button
          size="small"
          icon={<SyncOutlined />}
          loading={refreshMutation.isPending}
          onClick={handleRefresh}
        >
          刷新
        </Button>
      </div>
      <PaginatedList
        items={items}
        isLoading={isLoading}
        emptyText="暂无 Twitter 资讯"
        showSourceTag={true}
        pageSize={NEWS_PAGE_SIZE}
        searchQuery={searchQuery}
      />
    </div>
  );
}

function OtherNewsTab({ searchQuery = "" }: { searchQuery?: string }) {
  const { cardStyle } = useStyles();
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
  const [platform, setPlatform] = useState("all");
  const totalCount = items.length;

  const filteredItems = useMemo(() => {
    if (platform === "all") return items;
    const found = grouped.find(([k]) => k === platform);
    return found ? found[1] : [];
  }, [platform, grouped, items]);

  if (isLoading) {
    return (
      <div style={{ ...cardStyle, padding: "16px" }}>
        <Skeleton active paragraph={{ rows: 5 }} />
      </div>
    );
  }

  return (
    <div>
      {/* Platform filter bar — pills for top sources + dropdown for rest */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          marginBottom: 12,
          flexWrap: "wrap",
        }}
      >
        <Select
          value={platform}
          onChange={(v) => setPlatform(v)}
          size="small"
          style={{ minWidth: 140 }}
          options={[
            { value: "all", label: `全部 (${totalCount})` },
            ...grouped.map(([source, srcItems]) => ({
              value: source,
              label: `${source} (${srcItems.length})`,
            })),
          ]}
        />
      </div>
      <PaginatedList
        items={filteredItems}
        isLoading={isLoading}
        emptyText="暂无新闻"
        showSourceTag={true}
        pageSize={NEWS_PAGE_SIZE}
        searchQuery={searchQuery}
      />
    </div>
  );


}
/* ── 主页面 ────────────────────────────────────────────── */

export default function Feed() {
  const { pageContainerStyle, pageHeaderStyle, pageTitleStyle, pageDescriptionStyle } = useStyles();
  const isNarrow = useMediaQuery("(max-width: 1024px)");
  const [searchQuery, setSearchQuery] = React.useState("");
  return (
    <div style={pageContainerStyle}>
      <div style={pageHeaderStyle}>
        <Title level={3} style={pageTitleStyle}>24小时资讯</Title>
        <Paragraph style={pageDescriptionStyle}>
          实时聚合多源市场新闻，AI 智能提炼关键信息
        </Paragraph>
      </div>

      {/* Global search bar */}
      <Input.Search
        placeholder="搜索资讯标题或内容..."
        value={searchQuery}
        onChange={(e) => setSearchQuery(e.target.value)}
        onSearch={(v) => setSearchQuery(v)}
        allowClear
        style={{ marginBottom: 16 }}
      />

      {/* Two-column layout: tabs left, AI analysis right */}
      <div style={{ display: isNarrow ? "block" : "flex", gap: 16, alignItems: "flex-start" }}>
        {/* Left: Tabs */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <Tabs
            defaultActiveKey="kuaixun"
            size="large"
            items={[
              {
                key: "kuaixun",
                label: <span><ThunderboltOutlined /> 7×24 快讯</span>,
                children: <KuaixunTab searchQuery={searchQuery} />,
              },
              {
                key: "news",
                label: <span><ReadOutlined /> 新闻资讯</span>,
                children: <OtherNewsTab searchQuery={searchQuery} />,
              },
              {
                key: "twitter",
                label: <span>𝕏 Twitter</span>,
                children: <TwitterTab searchQuery={searchQuery} />,
              },
            ]}
            destroyInactiveTabPane
            style={{ background: "transparent" }}
          />
        </div>

        {/* Right: AI Analysis */}
        <div style={{ width: isNarrow ? "100%" : 340, flexShrink: 0, marginTop: isNarrow ? 16 : 0 }}>
          <NewsAnalysisPanel />
        </div>
      </div>
    </div>
  );
}
