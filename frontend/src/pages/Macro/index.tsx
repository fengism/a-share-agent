import { useState } from "react";
import { Tabs, Typography } from "antd";
import { DollarOutlined, LineChartOutlined, BankOutlined, FundOutlined, BarChartOutlined, GlobalOutlined } from "@ant-design/icons";
import PriceTab from "./PriceTab";
import PmiTab from "./PmiTab";
import MonetaryTab from "./MonetaryTab";
import RatesTab from "./RatesTab";
import GrowthTab from "./GrowthTab";
import TradeTab from "./TradeTab";
import { useStyles } from "../../styles/ui";;

const { Title, Paragraph } = Typography;

export default function Macro() {
  const { pageContainerStyle, pageDescriptionStyle, pageHeaderStyle, pageTitleStyle } = useStyles();
  const [activeTab, setActiveTab] = useState("prices");

  return (
    <div style={pageContainerStyle}>
      <div style={pageHeaderStyle}>
        <Title level={3} style={pageTitleStyle}>宏观经济</Title>
        <Paragraph style={pageDescriptionStyle}>
          物价、景气、货币、利率、增速、外贸六大类宏观指标一览。
        </Paragraph>
      </div>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        size="large"
        items={[
          {
            key: "prices",
            label: <span><DollarOutlined /> 物价指标</span>,
            children: <PriceTab />,
          },
          {
            key: "pmi",
            label: <span><LineChartOutlined /> 经济景气</span>,
            children: <PmiTab />,
          },
          {
            key: "monetary",
            label: <span><BankOutlined /> 货币金融</span>,
            children: <MonetaryTab />,
          },
          {
            key: "rates",
            label: <span><FundOutlined /> 利率</span>,
            children: <RatesTab />,
          },
          {
            key: "growth",
            label: <span><BarChartOutlined /> 经济增速</span>,
            children: <GrowthTab />,
          },
          {
            key: "trade",
            label: <span><GlobalOutlined /> 外贸</span>,
            children: <TradeTab />,
          },
        ]}
        style={{ background: "transparent" }}
      />
    </div>
  );
}
