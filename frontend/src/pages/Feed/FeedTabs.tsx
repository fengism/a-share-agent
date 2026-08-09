import { useMemo, useState } from "react";
import { ReadOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { Select, Tabs, Typography } from "antd";
import { useMarketKuaixun, useMarketOtherNews } from "../../api/queries";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import { useColors } from "../../styles/ui";
import type { FeedNewsItem } from "../../types/stock";
import { getSourcePlatform } from "./feedHelpers";
import PaginatedList from "./PaginatedList";

const { Text } = Typography;
const KUAIXUN_PAGE_SIZE = 30;
const NEWS_PAGE_SIZE = 20;
const FEED_TABS = ["kuaixun", "news"] as const;

function KuaixunTab({ searchQuery }: { searchQuery: string }) {
  const colors = useColors();
  const { data: items = [], isLoading, error, refetch } = useMarketKuaixun();

  return (
    <div>
      {!isLoading && items.length > 0 && (
        <div className="feed-tab-meta" style={{ justifyContent: "flex-end" }}>
          <Text style={{ color: colors.textSecondary, fontSize: 12 }}>共 {items.length} 条快讯</Text>
        </div>
      )}
      <PaginatedList
        items={items}
        isLoading={isLoading}
        emptyText="暂无快讯"
        showSourceTag={false}
        pageSize={KUAIXUN_PAGE_SIZE}
        searchQuery={searchQuery}
        error={error}
        onRetry={() => refetch()}
        errorTitle="快讯加载失败"
        layout="stream"
      />
    </div>
  );
}

function OtherNewsTab({ searchQuery }: { searchQuery: string }) {
  const { data: items = [], isLoading, error, refetch } = useMarketOtherNews();
  const [platform, setPlatform] = useState("all");

  const groupedItems = useMemo(() => {
    const groups = new Map<string, FeedNewsItem[]>();
    for (const item of items) {
      const sourcePlatform = getSourcePlatform(item.source);
      const group = groups.get(sourcePlatform);
      if (group) group.push(item);
      else groups.set(sourcePlatform, [item]);
    }
    return Array.from(groups.entries()).sort((left, right) => right[1].length - left[1].length);
  }, [items]);

  const filteredItems = useMemo(() => {
    if (platform === "all") return items;
    return groupedItems.find(([name]) => name === platform)?.[1] ?? [];
  }, [groupedItems, items, platform]);

  return (
    <div>
      <div className="feed-filter-bar">
        <Select
          value={platform}
          onChange={setPlatform}
          size="small"
          style={{ minWidth: 140, width: "min(100%, 240px)" }}
          options={[
            { value: "all", label: `全部 (${items.length})` },
            ...groupedItems.map(([source, sourceItems]) => ({
              value: source,
              label: `${source} (${sourceItems.length})`,
            })),
          ]}
        />
      </div>
      <PaginatedList
        items={filteredItems}
        isLoading={isLoading}
        emptyText="暂无新闻"
        showSourceTag
        pageSize={NEWS_PAGE_SIZE}
        searchQuery={searchQuery}
        error={error}
        onRetry={() => refetch()}
        errorTitle="新闻资讯加载失败"
        layout="editorial"
      />
    </div>
  );
}

export default function FeedTabs({ searchQuery }: { searchQuery: string }) {
  const [activeTab, setActiveTab] = useUrlSearchParam("tab", "kuaixun", { allowedValues: FEED_TABS });

  return (
    <Tabs
      className="feed-tabs"
      activeKey={activeTab}
      onChange={setActiveTab}
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
      ]}
      destroyOnHidden
      style={{ background: "transparent" }}
    />
  );
}
