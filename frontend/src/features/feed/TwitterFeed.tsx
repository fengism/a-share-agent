import { useEffect, useMemo, useState } from "react";
import { ClockCircleOutlined, SyncOutlined } from "@ant-design/icons";
import { Button, message, Typography } from "antd";
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
  const { data: items = [], dataUpdatedAt, isLoading, error, refetch } = useMarketTwitterFeed();
  const refreshMutation = useMarketTwitterFeedRefresh();
  const authors = useMemo(
    () => Array.from(new Set(
      items
        .map((item) => item.author?.trim())
        .filter((author): author is string => Boolean(author)),
    )),
    [items],
  );

  const handleRefresh = () => {
    refreshMutation.mutate(undefined, {
      onSuccess: () => message.success("Twitter 资讯已刷新"),
      onError: (refreshError) => message.error(refreshError?.message || "刷新失败"),
    });
  };

  return (
    <div className="feed-layout twitter-feed-layout">
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
        <PaginatedList
          items={items}
          isLoading={isLoading}
          emptyText="暂无 Twitter 资讯"
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
        <TwitterAnalysisPanel authors={authors} />
      </aside>
    </div>
  );
}
