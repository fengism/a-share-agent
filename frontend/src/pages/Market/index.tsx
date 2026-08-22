import { lazy, Suspense } from "react";
import { Segmented, Skeleton, Typography } from "antd";
import { FundOutlined, FireOutlined, LineChartOutlined, SwapRightOutlined, AppstoreOutlined, DashboardOutlined, ThunderboltOutlined } from "@ant-design/icons";
import ResponsiveSectionNav from "../../components/ResponsiveSectionNav";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import { useStyles } from "../../styles/ui";
import AIndexTab from "./AIndexTab";
import {
  loadDragonTigerTab,
  loadFundFlowTab,
  loadHotRankTab,
  loadIndustryRankTab,
  loadLimitUpLadderTab,
  loadMarketEmotionTab,
  loadMarketWindTab,
} from "./marketTabLoaders";

const FundFlowTab = lazy(loadFundFlowTab);
const MarketEmotionTab = lazy(loadMarketEmotionTab);
const MarketWindTab = lazy(loadMarketWindTab);
const LimitUpLadderTab = lazy(loadLimitUpLadderTab);
const IndustryRankTab = lazy(loadIndustryRankTab);
const HotRankTab = lazy(loadHotRankTab);
const DragonTigerTab = lazy(loadDragonTigerTab);

const { Title, Paragraph } = Typography;
const MARKET_TABS = ["a-index", "emotion", "today-wind", "limit-up", "fund-flow", "industry-rank", "rankings", "hot-rank", "dragon-tiger"] as const;
const RANKING_TABS = ["hot-rank", "dragon-tiger"] as const;

type RankingTab = (typeof RANKING_TABS)[number];

function preload(loader: () => Promise<unknown>) {
  void loader().catch(() => undefined);
}

function preloadRankings() {
  void Promise.all([loadHotRankTab(), loadDragonTigerTab()]).catch(() => undefined);
}

function TabFallback() {
  return (
    <div aria-label="市场模块加载中" style={{ minHeight: 480, padding: 24 }}>
      <Skeleton active paragraph={{ rows: 10 }} />
    </div>
  );
}

function RankingsPanel({ defaultRanking }: { defaultRanking: RankingTab }) {
  const [activeRanking, setActiveRanking] = useUrlSearchParam("ranking", defaultRanking, {
    allowedValues: RANKING_TABS,
  });

  return (
    <div>
      <Segmented
        aria-label="榜单类型"
        value={activeRanking}
        onChange={(value) => setActiveRanking(String(value))}
        options={[
          { value: "hot-rank", label: "热点榜单", icon: <FireOutlined /> },
          { value: "dragon-tiger", label: "龙虎榜", icon: <SwapRightOutlined style={{ transform: "rotate(90deg)" }} /> },
        ]}
        style={{ marginBottom: 16 }}
      />
      <Suspense fallback={<TabFallback />}>
        {activeRanking === "hot-rank" ? <HotRankTab /> : <DragonTigerTab />}
      </Suspense>
    </div>
  );
}

export default function Market() {
  const [tabParam, setActiveTab] = useUrlSearchParam("tab", "a-index", { allowedValues: MARKET_TABS });
  const activeTab = tabParam === "hot-rank" || tabParam === "dragon-tiger" ? "rankings" : tabParam;
  const defaultRanking: RankingTab = tabParam === "dragon-tiger" ? "dragon-tiger" : "hot-rank";
  const { pageContainerStyle, pageHeaderStyle, pageTitleStyle, pageDescriptionStyle } = useStyles();

  return (
    <div style={pageContainerStyle}>
      <div style={pageHeaderStyle}>
        <div className="u-page-title u-page-title--compact">
          <Title level={3} style={pageTitleStyle}>市场总览</Title>
        </div>
        <Paragraph style={pageDescriptionStyle}>查看核心指数、市场情绪、北向资金、热点榜单和龙虎榜，快速把握市场温度。</Paragraph>
      </div>
      <ResponsiveSectionNav
        activeKey={activeTab}
        onChange={setActiveTab}
        ariaLabel="市场数据分类"
        size="middle"
        tabBarGutter={12}
        collapseQuery="(max-width: 1024px)"
        items={[
          { key: "a-index", label: <span><FundOutlined /> A股大盘</span>, mobileLabel: "A股大盘", children: <Suspense fallback={<TabFallback />}><AIndexTab /></Suspense> },
          { key: "emotion", label: <span><DashboardOutlined /> 市场情绪</span>, mobileLabel: "市场情绪", onIntent: () => preload(loadMarketEmotionTab), children: <Suspense fallback={<TabFallback />}><MarketEmotionTab /></Suspense> },
          { key: "today-wind", label: <span><ThunderboltOutlined /> 今日风口</span>, mobileLabel: "今日风口", onIntent: () => preload(loadMarketWindTab), children: <Suspense fallback={<TabFallback />}><MarketWindTab /></Suspense> },
          { key: "limit-up", label: <span><FireOutlined /> 涨停板</span>, mobileLabel: "涨停板", onIntent: () => preload(loadLimitUpLadderTab), children: <Suspense fallback={<TabFallback />}><LimitUpLadderTab /></Suspense> },
          { key: "fund-flow", label: <span><LineChartOutlined /> 北向资金</span>, mobileLabel: "北向资金", onIntent: () => preload(loadFundFlowTab), children: <Suspense fallback={<TabFallback />}><FundFlowTab /></Suspense> },
          { key: "industry-rank", label: <span><AppstoreOutlined /> 板块涨跌幅</span>, mobileLabel: "板块涨跌幅", onIntent: () => preload(loadIndustryRankTab), children: <Suspense fallback={<TabFallback />}><IndustryRankTab /></Suspense> },
          { key: "rankings", label: <span><FireOutlined /> 榜单</span>, mobileLabel: "榜单", onIntent: preloadRankings, children: <RankingsPanel defaultRanking={defaultRanking} /> },
        ]}
      />
    </div>
  );
}
