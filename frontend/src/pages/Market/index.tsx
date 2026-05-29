import { useState } from "react";
import { Tabs, Typography } from "antd";
import { FundOutlined, FireOutlined, LineChartOutlined, SwapRightOutlined } from "@ant-design/icons";
import AIndexTab from "./AIndexTab";
import FundFlowTab from "./FundFlowTab";
import HotRankTab from "./HotRankTab";
import DragonTigerTab from "./DragonTigerTab";
import { pageContainerStyle, pageDescriptionStyle, pageHeaderStyle, pageTitleStyle } from "../../styles/ui";

const { Title, Paragraph } = Typography;

export default function Market() {
  const [activeTab, setActiveTab] = useState("a-index");

  return (
    <div style={pageContainerStyle}>
      <div style={pageHeaderStyle}>
        <Title level={3} style={pageTitleStyle}>市场总览</Title>
        <Paragraph style={pageDescriptionStyle}>查看核心指数、热点榜单和龙虎榜，快速把握市场温度。</Paragraph>
      </div>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        size="large"
        items={[
          {
            key: "a-index",
            label: <span><FundOutlined /> A股大盘</span>,
            children: <AIndexTab />,
          },
          {
            key: "fund-flow",
            label: <span><LineChartOutlined /> 资金流向</span>,
            children: <FundFlowTab />,
          },
          {
            key: "hot-rank",
            label: <span><FireOutlined /> 热点榜单</span>,
            children: <HotRankTab />,
          },
          {
            key: "dragon-tiger",
            label: <span><SwapRightOutlined style={{ transform: "rotate(90deg)" }} /> 龙虎榜</span>,
            children: <DragonTigerTab />,
          },
        ]}
        style={{ background: "transparent" }}
      />
    </div>
  );
}
