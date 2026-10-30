import { useMemo, useState } from "react";
import { SearchOutlined } from "@ant-design/icons";
import { Button, Card, Input, Space, Tag, Typography } from "antd";
import { useCategorizedStockNews } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { useColors, useStyles } from "../../styles/ui";
import type { StockNews } from "../../types/stock";

const { Text } = Typography;

const QUICK_FILTER_TAGS = ["全部", "业绩", "分红", "增持", "回购", "订单", "风险"];

function highlightKeyword(text: string, keyword: string) {
  if (!keyword.trim()) return text;
  const kw = keyword.trim();
  const lowerText = text.toLowerCase();
  const lowerKw = kw.toLowerCase();
  const parts: React.ReactNode[] = [];
  let start = 0;
  let idx = lowerText.indexOf(lowerKw, start);

  while (idx !== -1) {
    if (idx > start) {
      parts.push(text.slice(start, idx));
    }
    parts.push(
      <mark
        key={idx}
        style={{
          background: "rgba(250, 173, 20, 0.25)",
          color: "inherit",
          padding: "0 2px",
          borderRadius: 2,
        }}
      >
        {text.slice(idx, idx + kw.length)}
      </mark>
    );
    start = idx + kw.length;
    idx = lowerText.indexOf(lowerKw, start);
  }

  if (start < text.length) {
    parts.push(text.slice(start));
  }

  return <>{parts}</>;
}

function NewsList({ items, keyword, onClear }: { items: StockNews[]; keyword: string; onClear?: () => void }) {
  const colors = useColors();
  if (items.length === 0) {
    return (
      <div style={{ color: colors.textSecondary, padding: "16px 0", textAlign: "center" }}>
        {keyword ? (
          <div>
            <span>未找到包含 &ldquo;{keyword}&rdquo; 的相关资讯</span>
            {onClear && (
              <Button type="link" size="small" onClick={onClear} style={{ padding: "0 4px" }}>
                清空筛选
              </Button>
            )}
          </div>
        ) : (
          "暂无相关新闻"
        )}
      </div>
    );
  }
  return (
    <ul className="stock-information-list">
      {items.map((item, index) => (
        <li className="stock-information-list__item" key={`${item.url || item.publish_time}-${index}`}>
          {item.url ? (
            <a className="stock-information-list__title" href={item.url} target="_blank" rel="noreferrer">
              {highlightKeyword(item.title, keyword)}
            </a>
          ) : (
            <span className="stock-information-list__title">{highlightKeyword(item.title, keyword)}</span>
          )}
          <span className="stock-information-list__meta">
            {[item.source, item.publish_time].filter(Boolean).join(" · ") || "-"}
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function StockNewsPanel({ code }: { code: string }) {
  const query = useCategorizedStockNews(code);
  const { cardStyle } = useStyles();
  const [keyword, setKeyword] = useState("");
  const [activeTag, setActiveTag] = useState("全部");

  const eastmoneyNews = useMemo(() => query.data?.eastmoney_news ?? [], [query.data?.eastmoney_news]);
  const clsNews = useMemo(() => query.data?.cls_news ?? [], [query.data?.cls_news]);

  const handleTagClick = (tag: string) => {
    setActiveTag(tag);
    if (tag === "全部") {
      setKeyword("");
    } else {
      setKeyword(tag);
    }
  };

  const handleSearchChange = (value: string) => {
    setKeyword(value);
    if (!value) {
      setActiveTag("全部");
    } else {
      const matched = QUICK_FILTER_TAGS.find((t) => t !== "全部" && t === value.trim());
      setActiveTag(matched ?? "");
    }
  };

  const filteredCls = useMemo(() => {
    const kw = keyword.trim().toLowerCase();
    if (!kw) return clsNews;
    return clsNews.filter((item) =>
      item.title.toLowerCase().includes(kw) || (item.source && item.source.toLowerCase().includes(kw))
    );
  }, [clsNews, keyword]);

  const filteredEastmoney = useMemo(() => {
    const kw = keyword.trim().toLowerCase();
    if (!kw) return eastmoneyNews;
    return eastmoneyNews.filter((item) =>
      item.title.toLowerCase().includes(kw) || (item.source && item.source.toLowerCase().includes(kw))
    );
  }, [eastmoneyNews, keyword]);

  const clsTitle = keyword.trim()
    ? `财联社快讯（${filteredCls.length}/${clsNews.length}）`
    : `财联社快讯（${clsNews.length}）`;

  const eastmoneyTitle = keyword.trim()
    ? `东方财富资讯（${filteredEastmoney.length}/${eastmoneyNews.length}）`
    : `东方财富资讯（${eastmoneyNews.length}）`;

  return (
    <SectionDataState
      isLoading={query.isLoading}
      error={query.error}
      onRetry={() => query.refetch()}
      isEmpty={eastmoneyNews.length + clsNews.length === 0}
      emptyText="暂无相关新闻"
      errorTitle="新闻加载失败"
      minHeight={260}
    >
      <div style={{ marginBottom: 12, display: "flex", flexWrap: "wrap", alignItems: "center", gap: 10, justifyContent: "space-between" }}>
        <Space orientation="horizontal" size={6} wrap style={{ alignItems: "center" }}>
          <span style={{ fontSize: "var(--c-font-sm)", color: "var(--c-text-secondary)" }}>快捷筛选:</span>
          {QUICK_FILTER_TAGS.map((tag) => (
            <Tag.CheckableTag
              key={tag}
              checked={activeTag === tag}
              onChange={() => handleTagClick(tag)}
              style={{ cursor: "pointer" }}
            >
              {tag}
            </Tag.CheckableTag>
          ))}
        </Space>
        <Input
          placeholder="搜索新闻资讯关键词..."
          prefix={<SearchOutlined style={{ color: "var(--c-text-secondary)" }} />}
          allowClear
          value={keyword}
          onChange={(e) => handleSearchChange(e.target.value)}
          style={{ width: 220 }}
          size="small"
        />
      </div>
      <div className="stock-news-grid">
        <Card title={clsTitle} style={cardStyle} size="small" extra={<Text type="secondary">快讯</Text>}>
          <NewsList items={filteredCls} keyword={keyword} onClear={() => handleTagClick("全部")} />
        </Card>
        <Card title={eastmoneyTitle} style={cardStyle} size="small" extra={<Text type="secondary">资讯</Text>}>
          <NewsList items={filteredEastmoney} keyword={keyword} onClear={() => handleTagClick("全部")} />
        </Card>
      </div>
    </SectionDataState>
  );
}
