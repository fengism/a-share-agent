import { SearchOutlined } from "@ant-design/icons";
import { Input } from "antd";
import dayjs from "dayjs";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import { useStyles } from "../../styles/ui";
import FeedTabs from "./FeedTabs";
import NewsAnalysisPanel from "./NewsAnalysisPanel";
import "../../features/feed/feed.css";

export default function Feed() {
  const { pageContainerStyle } = useStyles();
  const [searchQuery, setSearchQuery] = useUrlSearchParam("q", "", { replace: true });

  return (
    <div style={{ ...pageContainerStyle, maxWidth: "var(--c-container-feed)" }}>
      <section className="feed-paper">
        <header className="feed-masthead">
          <span className="feed-masthead-kicker">A-SHARE INTELLIGENCE</span>
          <h1>市场资讯日报</h1>
          <div className="feed-masthead-meta">
            A 股资讯 · {dayjs().format("YYYY 年 MM 月 DD 日")} · 24 小时滚动更新
          </div>
        </header>

        <div className="feed-toolbar">
          <span className="feed-toolbar-label">聚合快讯、财经媒体与社交资讯</span>
          <Input
            className="feed-search"
            prefix={<SearchOutlined />}
            placeholder="搜索资讯标题或内容"
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            allowClear
            aria-label="搜索资讯标题或内容"
          />
        </div>

        <div className="feed-layout">
          <main className="feed-main-column">
          <FeedTabs searchQuery={searchQuery} />
          </main>
          <aside className="feed-rail">
            <NewsAnalysisPanel />
          </aside>
        </div>
      </section>
    </div>
  );
}
