import { lazy, Suspense } from "react";
import { Segmented, Skeleton, Typography } from "antd";
import { FundOutlined, FireOutlined, LineChartOutlined, SwapRightOutlined, AppstoreOutlined } from "@ant-design/icons";
import AIndexTab from "./AIndexTab";
import ResponsiveSectionNav from "../../components/ResponsiveSectionNav";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import { useStyles } from "../../styles/ui";

const FundFlowTab = lazy(() => import("./FundFlowTab"));
const IndustryRankTab = lazy(() => import("./IndustryRankTab"));
const HotRankTab = lazy(() => import("./HotRankTab"));
const DragonTigerTab = lazy(() => import("./DragonTigerTab"));

const { Title, Paragraph } = Typography;
const MARKET_TABS = ["a-index", "fund-flow", "industry-rank", "rankings", "hot-rank", "dragon-tiger"] as const;
const RANKING_TABS = ["hot-rank", "dragon-tiger"] as const;

type RankingTab = (typeof RANKING_TABS)[number];

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
        <Title level={3} style={pageTitleStyle}>市场总览</Title>
        <Paragraph style={pageDescriptionStyle}>查看核心指数、热点榜单和龙虎榜，快速把握市场温度。</Paragraph>
      </div>
      <ResponsiveSectionNav
        activeKey={activeTab}
        onChange={setActiveTab}
        ariaLabel="市场数据分类"
        items={[
          { key: "a-index", label: <span><FundOutlined /> A股大盘</span>, children: <AIndexTab /> },
          { key: "fund-flow", label: <span><LineChartOutlined /> 资金流向</span>, children: <Suspense fallback={<TabFallback />}><FundFlowTab /></Suspense> },
          { key: "industry-rank", label: <span><AppstoreOutlined /> 板块涨跌幅</span>, children: <Suspense fallback={<TabFallback />}><IndustryRankTab /></Suspense> },
          { key: "rankings", label: <span><FireOutlined /> 榜单</span>, children: <RankingsPanel defaultRanking={defaultRanking} /> },
        ]}
      />
    </div>
  );
}
