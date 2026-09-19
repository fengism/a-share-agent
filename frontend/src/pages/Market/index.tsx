import { lazy, Suspense } from "react";
import { Skeleton, Tabs, Tag, Typography } from "antd";
import {
  AlertOutlined,
  AppstoreOutlined,
  DashboardOutlined,
  HeatMapOutlined,
  FireOutlined,
  FundOutlined,
  LineChartOutlined,
  PayCircleOutlined,
  SwapRightOutlined,
} from "@ant-design/icons";
import { useIsTradingDay } from "../../api/queries";
import ResponsiveSectionNav from "../../components/ResponsiveSectionNav";
import RouteLoadingFallback from "../../components/RouteLoadingFallback";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import { useStyles } from "../../styles/ui";
import AIndexTab from "./AIndexTab";
import {
  loadDragonTigerTab,
  loadFundFlowTab,
  loadIndustryRankTab,
  loadLimitUpLadderTab,
  loadMarginTab,
  loadMarketBreadthTab,
  loadMarketEmotionTab,
  loadPriceAnomalyTab,
} from "./marketTabLoaders";
import "./market-page.css";

const HKMarketTab = lazy(() => import("../../features/hk-market/HKMarketTab"));
const FundFlowTab = lazy(loadFundFlowTab);
const MarginTab = lazy(loadMarginTab);
const MarketBreadthTab = lazy(loadMarketBreadthTab);
const MarketEmotionTab = lazy(loadMarketEmotionTab);
const LimitUpLadderTab = lazy(loadLimitUpLadderTab);
const IndustryRankTab = lazy(loadIndustryRankTab);
const DragonTigerTab = lazy(loadDragonTigerTab);
const PriceAnomalyTab = lazy(loadPriceAnomalyTab);

const { Title, Paragraph } = Typography;

const TOP_MARKET_TABS = ["a", "hk"] as const;
type TopMarketTabKey = (typeof TOP_MARKET_TABS)[number];

const MARKET_TABS = [
  "a-index",
  "emotion",
  "limit-up",
  "fund-flow",
  "margin",
  "breadth",
  "industry-rank",
  "dragon-tiger",
  "price-anomaly",
] as const;

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
  const [rawMarket, setRawMarket] = useUrlSearchParam("market", "a", {
    allowedValues: [...TOP_MARKET_TABS, "h"],
  });
  const activeMarket: TopMarketTabKey = rawMarket === "h" ? "hk" : (rawMarket as TopMarketTabKey);
  const [activeStockCode, setActiveStockCode] = useUrlSearchParam("code", "");

  const isTradingDay = useIsTradingDay();
  const [activeTab, setActiveTab] = useUrlSearchParam("tab", "a-index", { allowedValues: MARKET_TABS });
  const { pageContainerStyle, pageTitleStyle, pageDescriptionStyle } = useStyles();

  const aShareItems = [
    { key: "a-index", label: <span><FundOutlined /> A股大盘</span>, mobileLabel: "A股大盘", children: <Suspense fallback={<TabFallback />}><AIndexTab /></Suspense> },
    { key: "emotion", label: <span><DashboardOutlined /> 市场情绪</span>, mobileLabel: "市场情绪", onIntent: () => preload(loadMarketEmotionTab), children: <Suspense fallback={<TabFallback />}><MarketEmotionTab /></Suspense> },
    { key: "limit-up", label: <span><FireOutlined /> 涨停板</span>, mobileLabel: "涨停板", onIntent: () => preload(loadLimitUpLadderTab), children: <Suspense fallback={<TabFallback />}><LimitUpLadderTab /></Suspense> },
    { key: "fund-flow", label: <span><LineChartOutlined /> 北向资金</span>, mobileLabel: "北向资金", onIntent: () => preload(loadFundFlowTab), children: <Suspense fallback={<TabFallback />}><FundFlowTab /></Suspense> },
    { key: "margin", label: <span><PayCircleOutlined /> 融资融券</span>, mobileLabel: "融资融券", onIntent: () => preload(loadMarginTab), children: <Suspense fallback={<TabFallback />}><MarginTab /></Suspense> },
    { key: "breadth", label: <span><HeatMapOutlined /> 市场宽度</span>, mobileLabel: "市场宽度", onIntent: () => preload(loadMarketBreadthTab), children: <Suspense fallback={<TabFallback />}><MarketBreadthTab /></Suspense> },
    { key: "industry-rank", label: <span><AppstoreOutlined /> 板块涨跌幅</span>, mobileLabel: "板块涨跌幅", onIntent: () => preload(loadIndustryRankTab), children: <Suspense fallback={<TabFallback />}><IndustryRankTab /></Suspense> },
    { key: "dragon-tiger", label: <span><SwapRightOutlined style={{ transform: "rotate(90deg)" }} /> 龙虎榜</span>, mobileLabel: "龙虎榜", onIntent: () => preload(loadDragonTigerTab), children: <Suspense fallback={<TabFallback />}><DragonTigerTab /></Suspense> },
    { key: "price-anomaly", label: <span><AlertOutlined /> 交易所异动</span>, mobileLabel: "交易所异动", onIntent: () => preload(loadPriceAnomalyTab), children: <Suspense fallback={<TabFallback />}><PriceAnomalyTab /></Suspense> },
  ];
  const marketTabs = [
    {
      key: "a",
      label: (
        <span>
          <FundOutlined /> A股
        </span>
      ),
      children: (
        <ResponsiveSectionNav
          activeKey={activeTab}
          onChange={setActiveTab}
          ariaLabel="市场数据分类"
          size="middle"
          tabBarGutter={12}
          collapseQuery="(max-width: 1024px)"
          preserveVisited
          items={aShareItems}
        />
      ),
    },
    {
      key: "hk",
      label: (
        <span>
          <LineChartOutlined /> H股
        </span>
      ),
      children: (
        <Suspense fallback={<RouteLoadingFallback />}>
          <HKMarketTab
            embedded
            defaultStockCode={activeStockCode || undefined}
            onStockSelect={(code) => setActiveStockCode(code ?? "")}
          />
        </Suspense>
      ),
    },
  ];

  return (
    <div style={pageContainerStyle} className="market-page">
      <div className="market-page-header">
        <div>
          <div className="u-page-title u-page-title--compact">
            <Title level={3} style={pageTitleStyle}>
              <FundOutlined /> 市场
            </Title>
            {isTradingDay === false && (
              <Tag color="orange" style={{ marginInlineStart: 8 }}>
                今日非A股交易日
              </Tag>
            )}
          </div>
          <Paragraph style={pageDescriptionStyle}>
            查看A股大盘、市场情绪、资金动向、板块涨跌、龙虎榜与交易所异动，以及港股实时行情，快速把握市场温度。
          </Paragraph>
        </div>
      </div>

      <Tabs
        className="market-top-tabs"
        activeKey={activeMarket}
        onChange={(k) => setRawMarket(k)}
        items={marketTabs}
        size="large"
        destroyOnHidden={false}
      />
    </div>
  );
}
