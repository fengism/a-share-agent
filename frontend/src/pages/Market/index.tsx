import { lazy, Suspense } from "react";
import { Skeleton, Typography } from "antd";
import { FundOutlined, FireOutlined, LineChartOutlined, SwapRightOutlined, AppstoreOutlined, DashboardOutlined, PayCircleOutlined, CalendarOutlined } from "@ant-design/icons";
import ResponsiveSectionNav from "../../components/ResponsiveSectionNav";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import { useStyles } from "../../styles/ui";
import AIndexTab from "./AIndexTab";
import {
  loadDragonTigerTab,
  loadFundFlowTab,
  loadIndustryRankTab,
  loadLimitUpLadderTab,
  loadMarginTab,
  loadMarketEmotionTab,
  loadTradingCalendarTab,
} from "./marketTabLoaders";

const FundFlowTab = lazy(loadFundFlowTab);
const MarginTab = lazy(loadMarginTab);
const MarketEmotionTab = lazy(loadMarketEmotionTab);
const LimitUpLadderTab = lazy(loadLimitUpLadderTab);
const IndustryRankTab = lazy(loadIndustryRankTab);
const TradingCalendarTab = lazy(loadTradingCalendarTab);
const DragonTigerTab = lazy(loadDragonTigerTab);

const { Title, Paragraph } = Typography;
const MARKET_TABS = ["a-index", "emotion", "limit-up", "fund-flow", "margin", "industry-rank", "trading-calendar", "dragon-tiger"] as const;

function preload(loader: () => Promise<unknown>) {
  void loader().catch(() => undefined);
}

function TabFallback() {
  return (
    <div aria-label="市场模块加载中" style={{ minHeight: 480, padding: 24 }}>
      <Skeleton active paragraph={{ rows: 10 }} />
    </div>
  );
}

export default function Market() {
  const [activeTab, setActiveTab] = useUrlSearchParam("tab", "a-index", { allowedValues: MARKET_TABS });
  const { pageContainerStyle, pageHeaderStyle, pageTitleStyle, pageDescriptionStyle } = useStyles();

  return (
    <div style={pageContainerStyle}>
      <div style={pageHeaderStyle}>
        <div className="u-page-title u-page-title--compact">
          <Title level={3} style={pageTitleStyle}>市场总览</Title>
        </div>
        <Paragraph style={pageDescriptionStyle}>查看核心指数、市场情绪、北向资金、融资融券、板块涨跌和龙虎榜，快速把握市场温度。</Paragraph>
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
          { key: "limit-up", label: <span><FireOutlined /> 涨停板</span>, mobileLabel: "涨停板", onIntent: () => preload(loadLimitUpLadderTab), children: <Suspense fallback={<TabFallback />}><LimitUpLadderTab /></Suspense> },
          { key: "fund-flow", label: <span><LineChartOutlined /> 北向资金</span>, mobileLabel: "北向资金", onIntent: () => preload(loadFundFlowTab), children: <Suspense fallback={<TabFallback />}><FundFlowTab /></Suspense> },
          { key: "margin", label: <span><PayCircleOutlined /> 融资融券</span>, mobileLabel: "融资融券", onIntent: () => preload(loadMarginTab), children: <Suspense fallback={<TabFallback />}><MarginTab /></Suspense> },
          { key: "industry-rank", label: <span><AppstoreOutlined /> 板块涨跌幅</span>, mobileLabel: "板块涨跌幅", onIntent: () => preload(loadIndustryRankTab), children: <Suspense fallback={<TabFallback />}><IndustryRankTab /></Suspense> },
          { key: "trading-calendar", label: <span><CalendarOutlined /> 交易日历</span>, mobileLabel: "交易日历", onIntent: () => preload(loadTradingCalendarTab), children: <Suspense fallback={<TabFallback />}><TradingCalendarTab /></Suspense> },
          { key: "dragon-tiger", label: <span><SwapRightOutlined style={{ transform: "rotate(90deg)" }} /> 龙虎榜</span>, mobileLabel: "龙虎榜", onIntent: () => preload(loadDragonTigerTab), children: <Suspense fallback={<TabFallback />}><DragonTigerTab /></Suspense> },
        ]}
      />
    </div>
  );
}
