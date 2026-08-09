import { useEffect, useMemo, useState } from "react";
import { ClockCircleOutlined, SearchOutlined, SyncOutlined } from "@ant-design/icons";
import { Button, Input, message, Typography } from "antd";
import dayjs from "dayjs";
import relativeTime from "dayjs/plugin/relativeTime";
import "dayjs/locale/zh-cn";
import { useMarketTwitterFeed, useMarketTwitterFeedRefresh } from "../../api/queries";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import { useColors, useStyles } from "../../styles/ui";
import { getRelativeTimeRefreshDelay } from "../Feed/feedHelpers";
import PaginatedList from "../Feed/PaginatedList";
import TwitterAnalysisPanel from "./TwitterAnalysisPanel";
import "../Feed/feed.css";

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
    <Text style={{ color: colors.textSecondary, fontSize: 12 }}>
      <ClockCircleOutlined style={{ marginRight: 4 }} />
      页面同步 {dayjs(updatedAt).fromNow()}
      {itemCount > 0 && <span style={{ marginLeft: 8 }}>· 共 {itemCount} 条</span>}
    </Text>
  );
}

export default function Twitter() {
  const { pageContainerStyle } = useStyles();
  const [searchQuery, setSearchQuery] = useUrlSearchParam("q", "", { replace: true });
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
    <div style={{ ...pageContainerStyle, maxWidth: 1180 }}>
      <section className="feed-paper">
        <header className="feed-masthead">
          <span className="feed-masthead-kicker">SOCIAL MARKET SIGNALS</span>
          <h1>Twitter 财经动态</h1>
          <div className="feed-masthead-meta">财经账号聚合 · 每 12 小时自动更新</div>
        </header>

        <div className="feed-toolbar">
          <span className="feed-toolbar-label">追踪已配置 Twitter/X 财经账号的最新推文与文章</span>
          <Input
            className="feed-search"
            prefix={<SearchOutlined />}
            placeholder="搜索推文标题或内容"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            allowClear
            aria-label="搜索 Twitter 资讯"
          />
        </div>

        <div className="feed-layout twitter-feed-layout">
          <main className="feed-main-column">
            <div className="feed-tab-meta">
              <RelativeRefreshTime updatedAt={dataUpdatedAt} itemCount={items.length} />
              <div className="twitter-feed-refresh">
                <Text type="secondary">源数据每 12 小时自动刷新</Text>
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
      </section>
    </div>
  );
}
