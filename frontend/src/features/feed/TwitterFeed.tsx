import { useEffect, useMemo, useState } from "react";
import { ClockCircleOutlined, FilterOutlined, SyncOutlined, UserOutlined } from "@ant-design/icons";
import { Button, message, Segmented, Typography } from "antd";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import "dayjs/locale/zh-cn";
import { useMarketTwitterFeed, useMarketTwitterFeedRefresh } from "../../api/queries";
import { useColors } from "../../styles/ui";
import { getRelativeTimeRefreshDelay } from "./feedHelpers";
import PaginatedList from "./PaginatedList";
import TwitterAnalysisPanel from "./TwitterAnalysisPanel";
import "./feed.css";

dayjs.extend(relativeTime);
dayjs.locale("zh-cn");

const { Text } = Typography;
const PAGE_SIZE = 20;

function RelativeRefreshTime({ updatedAt, itemCount }: { updatedAt: number; itemCount: number }) {
  const colors = useColors();
  const [, setTick] = useState(0);

  useEffect(() => {
    if (updatedAt <= 0) return;
    let timeoutId: number;
    const scheduleNextUpdate = () => {
      timeoutId = window.setTimeout(() => {
        setTick((current) => current + 1);
        scheduleNextUpdate();
      }, getRelativeTimeRefreshDelay(Date.now()));
    };
    scheduleNextUpdate();
    return () => window.clearTimeout(timeoutId);
  }, [updatedAt]);

  if (updatedAt <= 0) return null;

  return (
    <Text style={{ color: colors.textSecondary, fontSize: "var(--c-font-sm)" }}>
      <ClockCircleOutlined style={{ marginRight: 4 }} />
      页面同步 {dayjs(updatedAt).fromNow()}
      {itemCount > 0 && <span style={{ marginLeft: 8 }}>· 共 {itemCount} 条</span>}
    </Text>
  );
}

export default function TwitterFeed({ searchQuery }: { searchQuery: string }) {
  const [mobileTab, setMobileTab] = useState<"tweets" | "analysis">("tweets");
  const [selectedAuthor, setSelectedAuthor] = useState<string>("");
  const { data: items = [], dataUpdatedAt, isLoading, error, refetch } = useMarketTwitterFeed();
  const refreshMutation = useMarketTwitterFeedRefresh();

  const authorCounts = useMemo(() => {
    const map = new Map<string, number>();
    for (const item of items) {
      const author = item.author?.trim();
      if (author) {
        map.set(author, (map.get(author) || 0) + 1);
      }
    }
    return map;
  }, [items]);

  const authors = useMemo(() => Array.from(authorCounts.keys()), [authorCounts]);

  const displayedItems = useMemo(() => {
    if (!selectedAuthor) return items;
    return items.filter((item) => item.author?.trim() === selectedAuthor);
  }, [items, selectedAuthor]);

  const handleRefresh = () => {
    refreshMutation.mutate(undefined, {
      onSuccess: () => message.success("Twitter 资讯已刷新"),
      onError: (refreshError) => message.error(refreshError?.message || "刷新失败"),
    });
  };

  return (
    <div className="feed-layout twitter-feed-layout" data-mobile-tab={mobileTab}>
      <div className="twitter-mobile-nav">
        <Segmented
          block
          value={mobileTab}
          onChange={(val) => setMobileTab(val as "tweets" | "analysis")}
          options={[
            { label: `💬 推文动态 (${displayedItems.length})`, value: "tweets" },
            { label: "🤖 AI 大 V 核心解读", value: "analysis" },
          ]}
        />
      </div>

      <main className="feed-main-column">
        <div className="feed-tab-meta">
          <RelativeRefreshTime updatedAt={dataUpdatedAt} itemCount={items.length} />
          <div className="twitter-feed-refresh">
            <Text type="secondary">每 12 小时更新</Text>
            <Button
              size="small"
              icon={<SyncOutlined />}
              loading={refreshMutation.isPending}
              onClick={handleRefresh}
            >
              立即刷新
            </Button>
          </div>
        </div>

        {authors.length > 0 && (
          <div className="twitter-author-pills" role="navigation" aria-label="大 V 筛选">
            <span className="twitter-pills-label">
              <FilterOutlined style={{ marginRight: 4 }} />
              大 V 聚焦：
            </span>
            <button
              type="button"
              className={`twitter-pill ${!selectedAuthor ? "is-active" : ""}`}
              onClick={() => setSelectedAuthor("")}
            >
              全部 ({items.length})
            </button>
            {authors.map((author) => (
              <button
                key={author}
                type="button"
                className={`twitter-pill ${selectedAuthor === author ? "is-active" : ""}`}
                onClick={() => setSelectedAuthor(selectedAuthor === author ? "" : author)}
              >
                <UserOutlined style={{ marginRight: 3, fontSize: 11 }} />
                @{author} ({authorCounts.get(author)})
              </button>
            ))}
          </div>
        )}

        <PaginatedList
          items={displayedItems}
          isLoading={isLoading}
          emptyText={selectedAuthor ? "该作者暂无推文" : "暂无 Twitter 资讯"}
          showSourceTag
          pageSize={PAGE_SIZE}
          searchQuery={searchQuery}
          error={error}
          onRetry={() => refetch()}
          errorTitle="Twitter 资讯加载失败"
          layout="editorial"
        />
      </main>

      <aside className="feed-rail">
        <TwitterAnalysisPanel
          authors={authors}
          selectedAuthor={selectedAuthor || undefined}
          onSelectAuthor={setSelectedAuthor}
        />
      </aside>
    </div>
  );
}
