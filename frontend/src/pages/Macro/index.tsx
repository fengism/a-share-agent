import { lazy, Suspense } from "react";
import { Button, Typography, message } from "antd";
import { DollarOutlined, LineChartOutlined, BankOutlined, FundOutlined, BarChartOutlined, GlobalOutlined, ReloadOutlined } from "@ant-design/icons";
import { useForceRefreshMacroAllData } from "../../api/queries";
import ResponsiveSectionNav from "../../components/ResponsiveSectionNav";
import PriceTab from "./PriceTab";
import PmiTab from "./PmiTab";
import MonetaryTab from "./MonetaryTab";
import RatesTab from "./RatesTab";
import GrowthTab from "./GrowthTab";
import TradeTab from "./TradeTab";
import { useStyles } from "../../styles/ui";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";

const { Title, Paragraph } = Typography;
const UsMacroTab = lazy(() => import("./UsMacroTab"));
const MACRO_TABS = ["prices", "pmi", "monetary", "rates", "growth", "trade", "us"] as const;

export default function Macro() {
  const { pageContainerStyle, pageDescriptionStyle, pageHeaderStyle, pageTitleStyle } = useStyles();
  const [activeTab, setActiveTab] = useUrlSearchParam("tab", "prices", { allowedValues: MACRO_TABS });
  const refreshMacroData = useForceRefreshMacroAllData();

  const handleForceRefresh = () => {
    refreshMacroData.mutate(undefined, {
      onSuccess: () => message.success("宏观数据已刷新"),
      onError: (error: Error) => message.error(`刷新失败: ${error.message}`),
    });
  };

  return (
    <div style={pageContainerStyle}>
      <div style={{ ...pageHeaderStyle, display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
        <div>
          <div className="u-page-title u-page-title--compact">
            <Title level={3} style={pageTitleStyle}>宏观经济</Title>
          </div>
          <Paragraph style={pageDescriptionStyle}>
            物价、景气、货币、利率、增速、外贸六大类宏观指标一览。
          </Paragraph>
        </div>
        <Button
          icon={<ReloadOutlined />}
          loading={refreshMacroData.isPending}
          onClick={handleForceRefresh}
        >
          强制刷新
        </Button>
      </div>
      <ResponsiveSectionNav
        activeKey={activeTab}
        onChange={setActiveTab}
        ariaLabel="宏观经济指标分类"
        desktopMode="rail"
        items={[
          {
            key: "prices",
            label: <span><DollarOutlined /> 物价指标</span>,
            mobileLabel: "物价指标",
            group: "经济运行",
            children: <PriceTab />,
          },
          {
            key: "pmi",
            label: <span><LineChartOutlined /> 经济景气</span>,
            mobileLabel: "经济景气",
            group: "经济运行",
            children: <PmiTab />,
          },
          {
            key: "growth",
            label: <span><BarChartOutlined /> 经济增速</span>,
            mobileLabel: "经济增速",
            group: "经济运行",
            children: <GrowthTab />,
          },
          {
            key: "trade",
            label: <span><GlobalOutlined /> 外贸</span>,
            mobileLabel: "外贸",
            group: "经济运行",
            children: <TradeTab />,
          },
          {
            key: "us",
            label: <span><GlobalOutlined /> 美国宏观</span>,
            mobileLabel: "美国宏观",
            group: "全球市场",
            children: <Suspense fallback={<div>正在加载美国宏观数据…</div>}><UsMacroTab /></Suspense>,
          },
          {
            key: "monetary",
            label: <span><BankOutlined /> 货币金融</span>,
            mobileLabel: "货币金融",
            group: "金融环境",
            children: <MonetaryTab />,
          },
          {
            key: "rates",
            label: <span><FundOutlined /> 利率</span>,
            mobileLabel: "利率",
            group: "金融环境",
            children: <RatesTab />,
          },
        ]}
      />
    </div>
  );
}
