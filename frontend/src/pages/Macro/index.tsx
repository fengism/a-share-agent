import { lazy, Suspense } from "react";
import { Button, Typography, message } from "antd";
import {
  AppstoreOutlined,
  DollarOutlined,
  LineChartOutlined,
  BankOutlined,
  FundOutlined,
  GoldOutlined,
  BarChartOutlined,
  GlobalOutlined,
  ReloadOutlined,
  FireOutlined,
  CompassOutlined,
} from "@ant-design/icons";
import { useForceRefreshMacroAllData } from "../../api/queries";
import ResponsiveSectionNav from "../../components/ResponsiveSectionNav";
import DomesticMacroOverview from "./DomesticMacroOverview";
import PriceTab from "./PriceTab";
import PmiTab from "./PmiTab";
import FinanceTab from "./FinanceTab";
import RatesTab from "./RatesTab";
import GrowthTab from "./GrowthTab";
import TradeTab from "./TradeTab";
import GlobalRatesTab from "./GlobalRatesTab";
import CommoditiesTab from "./CommoditiesTab";
import SgeGoldTab from "./SgeGoldTab";
import { useStyles } from "../../styles/ui";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import "./macro-page.css";

const { Title, Paragraph } = Typography;
const UsMacroTab = lazy(() => import("./UsMacroTab"));
const MACRO_TABS = [
  "overview",
  "growth",
  "prices",
  "pmi",
  "monetary",
  "rates",
  "trade",
  "commodities",
  "sge_gold",
  "global_rates",
  "us",
] as const;

export default function Macro() {
  const { pageContainerStyle } = useStyles();
  const [activeTab, setActiveTab] = useUrlSearchParam("tab", "overview", { allowedValues: MACRO_TABS });
  const refreshMacroData = useForceRefreshMacroAllData();

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
            聚合国内产出增长、物价通胀、景气周期、海关出海量价、大宗工业品现货基差、中美利差与全球流动性利率，一站式洞察宏观大周期。
          </Paragraph>
          <div className="macro-page__scope" aria-label="数据覆盖范围">
            <span>10 大主题</span>
            <span>大宗现货 & 海关出海</span>
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
        items={[
          {
            key: "overview",
            label: <span><AppstoreOutlined /> 宏观总览</span>,
            mobileLabel: "宏观总览",
            group: "国内宏观",
            children: <DomesticMacroOverview />,
          },
          {
            key: "growth",
            label: <span><BarChartOutlined /> 经济增长</span>,
            mobileLabel: "经济增长",
            group: "国内宏观",
            children: <GrowthTab />,
          },
          {
            key: "prices",
            label: <span><DollarOutlined /> 物价通胀</span>,
            mobileLabel: "物价通胀",
            group: "国内宏观",
            children: <PriceTab />,
          },
          {
            key: "pmi",
            label: <span><LineChartOutlined /> 景气监测</span>,
            mobileLabel: "景气监测",
            group: "国内宏观",
            children: <PmiTab />,
          },
          {
            key: "monetary",
            label: <span><BankOutlined /> 金融流动性</span>,
            mobileLabel: "金融流动性",
            group: "国内宏观",
            children: <FinanceTab />,
          },
          {
            key: "trade",
            label: <span><GlobalOutlined /> 海关与出海</span>,
            mobileLabel: "海关与出海",
            group: "国内宏观",
            children: <TradeTab />,
          },
          {
            key: "rates",
            label: <span><FundOutlined /> 资金利率</span>,
            mobileLabel: "资金利率",
            group: "国内宏观",
            children: <RatesTab />,
          },
          {
            key: "commodities",
            label: <span><FireOutlined /> 大宗商品现货</span>,
            mobileLabel: "大宗商品现货",
            group: "工业品大宗",
            children: <CommoditiesTab />,
          },
          {
            key: "sge_gold",
            label: <span><GoldOutlined /> 上金所黄金走势</span>,
            mobileLabel: "黄金走势",
            group: "工业品大宗",
            children: <SgeGoldTab />,
          },
          {
            key: "global_rates",
            label: <span><CompassOutlined /> 全球利率与汇率</span>,
            mobileLabel: "全球利率与汇率",
            group: "全球市场",
            children: <GlobalRatesTab />,
          },
          {
            key: "us",
            label: <span><GlobalOutlined /> 美国宏观</span>,
            mobileLabel: "美国宏观",
            group: "全球市场",
            children: <Suspense fallback={<div className="macro-page__loading">正在加载美国宏观数据…</div>}><UsMacroTab /></Suspense>,
          },
        ]}
      />
    </div>
  );
}
