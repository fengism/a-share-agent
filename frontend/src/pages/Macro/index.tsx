import { lazy, Suspense, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { Button, Skeleton, Typography, message } from "antd";
import {
  AppstoreOutlined,
  DollarOutlined,
  LineChartOutlined,
  BankOutlined,
  GoldOutlined,
  BarChartOutlined,
  GlobalOutlined,
  ReloadOutlined,
  FireOutlined,
  CompassOutlined,
  ExportOutlined,
} from "@ant-design/icons";
import { useForceRefreshMacroAllData } from "../../api/queries";
import ResponsiveSectionNav from "../../components/ResponsiveSectionNav";
import { useStyles } from "../../styles/ui";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import "./macro-page.css";

const DomesticMacroOverview = lazy(() => import("./DomesticMacroOverview"));
const PriceTab = lazy(() => import("./PriceTab"));
const PmiTab = lazy(() => import("./PmiTab"));
const FinanceTab = lazy(() => import("./FinanceTab"));
const GrowthTab = lazy(() => import("./GrowthTab"));
const TradeTab = lazy(() => import("./TradeTab"));
const GlobalRatesTab = lazy(() => import("./GlobalRatesTab"));
const CommoditiesTab = lazy(() => import("./CommoditiesTab"));
const SgeGoldTab = lazy(() => import("./SgeGoldTab"));
const UsMacroTab = lazy(() => import("./UsMacroTab"));

function TabFallback() {
  return (
    <div aria-label="宏观模块加载中" style={{ minHeight: 420, padding: 20 }}>
      <Skeleton active paragraph={{ rows: 8 }} />
    </div>
  );
}
const { Title, Paragraph } = Typography;

const MACRO_TABS = [
  "overview",
  "growth",
  "pmi",
  "prices",
  "trade",
  "monetary",
  "global_rates",
  "commodities",
  "sge_gold",
  "us",
] as const;

export default function Macro() {
  const { pageContainerStyle } = useStyles();
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useUrlSearchParam("tab", "overview", { allowedValues: MACRO_TABS });
  const refreshMacroData = useForceRefreshMacroAllData();

  // 兼容旧版 ?tab=rates 链接：资金利率已全面整合进金融流动性，平滑重定向至 monetary
  useEffect(() => {
    if (searchParams.get("tab") === "rates") {
      setSearchParams(
        (current) => {
          const next = new URLSearchParams(current);
          next.set("tab", "monetary");
          return next;
        },
        { replace: true },
      );
    }
  }, [searchParams, setSearchParams]);

  const handleForceRefresh = () => {
    refreshMacroData.mutate(undefined, {
      onSuccess: () => message.success("宏观数据已刷新"),
      onError: (error: Error) => message.error(`刷新失败: ${error.message}`),
    });
  };

  return (
    <div className="macro-page" style={pageContainerStyle}>
      <header className="macro-page__header">
        <div className="macro-page__heading">
          <div className="macro-page__eyebrow">MACRO OVERVIEW · 宏观经济与大宗商品分析</div>
          <div className="u-page-title u-page-title--compact macro-page__title-wrap">
            <Title level={3} className="macro-page__title">宏观经济</Title>
          </div>
          <Paragraph className="macro-page__description">
            聚合国内产出增长、物价通胀、景气周期、全国进出口总量、大宗商品期货行情、中美利差与全球流动性利率，一站式洞察宏观大周期。
          </Paragraph>
          <div className="macro-page__scope" aria-label="数据覆盖范围">
            <span>10 大主题</span>
            <span>商品期货 & 全国进出口</span>
            <span>全球利差 & 美债折现率</span>
          </div>
        </div>
        <Button
          className="macro-page__refresh"
          icon={<ReloadOutlined />}
          loading={refreshMacroData.isPending}
          onClick={handleForceRefresh}
        >
          强制刷新
        </Button>
      </header>
      <ResponsiveSectionNav
        activeKey={activeTab}
        onChange={setActiveTab}
        ariaLabel="宏观经济指标分类"
        desktopMode="rail"
        collapseQuery="(max-width: 959px)"
        preserveVisited
        items={[
          {
            key: "overview",
            label: <span><AppstoreOutlined /> 宏观总览</span>,
            mobileLabel: "宏观总览",
            group: "综合看板",
            children: <Suspense fallback={<TabFallback />}><DomesticMacroOverview /></Suspense>,
          },
          {
            key: "growth",
            label: <span><BarChartOutlined /> 经济增长</span>,
            mobileLabel: "经济增长",
            group: "实体与景气",
            children: <Suspense fallback={<TabFallback />}><GrowthTab /></Suspense>,
          },
          {
            key: "pmi",
            label: <span><LineChartOutlined /> 景气监测</span>,
            mobileLabel: "景气监测",
            group: "实体与景气",
            children: <Suspense fallback={<TabFallback />}><PmiTab /></Suspense>,
          },
          {
            key: "prices",
            label: <span><DollarOutlined /> 物价通胀</span>,
            mobileLabel: "物价通胀",
            group: "实体与景气",
            children: <Suspense fallback={<TabFallback />}><PriceTab /></Suspense>,
          },
          {
            key: "trade",
            label: <span><ExportOutlined /> 海关与出海</span>,
            mobileLabel: "海关与出海",
            group: "实体与景气",
            children: <Suspense fallback={<TabFallback />}><TradeTab /></Suspense>,
          },
          {
            key: "monetary",
            label: <span><BankOutlined /> 金融流动性</span>,
            mobileLabel: "金融流动性",
            group: "流动性与利率",
            children: <Suspense fallback={<TabFallback />}><FinanceTab /></Suspense>,
          },
          {
            key: "global_rates",
            label: <span><CompassOutlined /> 全球利率与外汇</span>,
            mobileLabel: "全球利率与外汇",
            group: "流动性与利率",
            children: <Suspense fallback={<TabFallback />}><GlobalRatesTab /></Suspense>,
          },
          {
            key: "commodities",
            label: <span><FireOutlined /> 大宗商品期货</span>,
            mobileLabel: "大宗商品期货",
            group: "大宗与海外",
            children: <Suspense fallback={<TabFallback />}><CommoditiesTab /></Suspense>,
          },
          {
            key: "sge_gold",
            label: <span><GoldOutlined /> 上金所黄金走势</span>,
            mobileLabel: "黄金走势",
            group: "大宗与海外",
            children: <Suspense fallback={<TabFallback />}><SgeGoldTab /></Suspense>,
          },
          {
            key: "us",
            label: <span><GlobalOutlined /> 美国宏观</span>,
            mobileLabel: "美国宏观",
            group: "大宗与海外",
            children: <Suspense fallback={<TabFallback />}><UsMacroTab /></Suspense>,
          },
        ]}
      />
    </div>
  );
}
