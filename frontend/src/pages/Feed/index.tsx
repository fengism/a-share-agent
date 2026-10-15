import { ReadOutlined, SearchOutlined, TwitterOutlined, FundOutlined } from "@ant-design/icons";
import { Input, Tabs } from "antd";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import { useStyles } from "../../styles/ui";
import MacroFeed from "../../features/feed/MacroFeed";
import TwitterFeed from "../../features/feed/TwitterFeed";
import FeedTabs from "./FeedTabs";
import NewsAnalysisPanel from "./NewsAnalysisPanel";
import "../../features/feed/feed.css";

const FEED_SECTIONS = ["market", "macro", "twitter"] as const;
type FeedSection = (typeof FEED_SECTIONS)[number];

const SECTION_SEARCH: Record<FeedSection, {
  placeholder: string;
  label: string;
}> = {
  market: {
    placeholder: "搜索资讯标题或内容",
    label: "搜索市场资讯",
  },
  macro: {
    placeholder: "搜索宏观数据或政策",
    label: "搜索宏观数据",
  },
  twitter: {
    placeholder: "搜索推文标题或内容",
    label: "搜索 Twitter 资讯",
  },
};

function MarketFeed({ searchQuery }: { searchQuery: string }) {
  return (
    <div className="feed-layout">
      <main className="feed-main-column">
        <FeedTabs searchQuery={searchQuery} />
      </main>
      <aside className="feed-rail">
        <NewsAnalysisPanel />
      </aside>
    </div>
  );
}

export default function Feed() {
  const { pageContainerStyle } = useStyles();
  const [activeSection, setActiveSection] = useUrlSearchParam<FeedSection>("tab", "market", {
    allowedValues: FEED_SECTIONS,
  });
  const [searchQuery, setSearchQuery] = useUrlSearchParam("q", "", { replace: true });
  const searchConfig = SECTION_SEARCH[activeSection];

  return (
    <div style={{ ...pageContainerStyle, maxWidth: "var(--c-container-feed)" }}>
      <section className="feed-paper">
        <header className="feed-masthead">
          <span className="feed-masthead-kicker">A-SHARE INTELLIGENCE</span>
          <h1>资讯中心</h1>
          <div className="feed-masthead-meta">聚合市场快讯、财经媒体与社交信号</div>
        </header>

        <Tabs
          className="feed-source-tabs"
          activeKey={activeSection}
          onChange={setActiveSection}
          size="large"
          tabBarExtraContent={(
            <Input
              className="feed-search"
              prefix={<SearchOutlined />}
              placeholder={searchConfig.placeholder}
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              allowClear
              aria-label={searchConfig.label}
            />
          )}
          items={[
            {
              key: "market",
              label: <span><ReadOutlined /> 市场资讯</span>,
              children: <MarketFeed searchQuery={searchQuery} />,
            },
            {
              key: "macro",
              label: <span><FundOutlined /> 宏观数据</span>,
              children: <MacroFeed searchQuery={searchQuery} />,
            },
            {
              key: "twitter",
              label: <span><TwitterOutlined /> Twitter 资讯</span>,
              children: <TwitterFeed searchQuery={searchQuery} />,
            },
          ]}
          destroyOnHidden
        />
      </section>
    </div>
  );
}
