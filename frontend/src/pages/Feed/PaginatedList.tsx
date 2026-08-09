import { useEffect, useMemo, useState } from "react";
import { Empty, Pagination, Skeleton } from "antd";
import QueryErrorState from "../../components/QueryErrorState";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import type { FeedNewsItem } from "../../types/stock";
import { clampPage } from "./feedHelpers";
import NewsListItem from "./NewsListItem";
import type { FeedItemLayout } from "./NewsListItem";

interface PaginatedListProps {
  items: FeedNewsItem[];
  isLoading: boolean;
  emptyText: string;
  showSourceTag: boolean;
  pageSize: number;
  searchQuery?: string;
  error?: unknown;
  onRetry?: () => unknown;
  errorTitle?: string;
  layout: FeedItemLayout;
}

export default function PaginatedList({
  items,
  isLoading,
  emptyText,
  showSourceTag,
  pageSize,
  searchQuery = "",
  error,
  onRetry,
  errorTitle = "资讯加载失败",
  layout,
}: PaginatedListProps) {
  const isNarrow = useMediaQuery("(max-width: 640px)");
  const [page, setPage] = useState(1);

  const filteredItems = useMemo(() => {
    if (!searchQuery) return items;
    const normalizedQuery = searchQuery.toLowerCase();
    return items.filter((item) =>
      (item.title && item.title.toLowerCase().includes(normalizedQuery))
      || (item.content && item.content.toLowerCase().includes(normalizedQuery)),
    );
  }, [items, searchQuery]);

  const total = filteredItems.length;
  const totalPages = Math.ceil(total / pageSize);
  const currentPage = clampPage(page, total, pageSize);
  const start = (currentPage - 1) * pageSize;
  const pageItems = filteredItems.slice(start, start + pageSize);

  useEffect(() => {
    setPage(1);
  }, [searchQuery]);

  useEffect(() => {
    setPage((current) => clampPage(current, total, pageSize));
  }, [pageSize, total]);

  if (isLoading && items.length === 0) {
    return (
      <div className="feed-state">
        <Skeleton active paragraph={{ rows: 5 }} />
      </div>
    );
  }

  if (error && items.length === 0) {
    return (
      <div className="feed-state">
        <QueryErrorState error={error} onRetry={onRetry} title={errorTitle} />
      </div>
    );
  }

  if (total === 0) {
    return <Empty description={emptyText} style={{ padding: "60px 0" }} />;
  }

  return (
    <div className="feed-list-surface">
      <div className={layout === "editorial" ? "feed-news-grid" : "feed-stream-list"}>
        {pageItems.map((item, index) => (
          <NewsListItem
            key={`${item.url || item.title}-${item.publish_time}-${index}`}
            item={item}
            showSourceTag={showSourceTag}
            layout={layout}
            featured={layout === "editorial" && index === 0}
          />
        ))}
      </div>
      {totalPages > 1 && (
        <div className="feed-pagination">
          <Pagination
            current={currentPage}
            total={total}
            pageSize={pageSize}
            onChange={(nextPage) => {
              window.scrollTo({ top: 0, behavior: "smooth" });
              setPage(nextPage);
            }}
            size="small"
            showSizeChanger={false}
            showLessItems={isNarrow}
            responsive
            showTotal={isNarrow ? undefined : (count) => `共 ${count} 条`}
          />
        </div>
      )}
    </div>
  );
}
