import { useState } from "react";
import { FileTextOutlined, GlobalOutlined, LineChartOutlined, ReadOutlined } from "@ant-design/icons";
import { Card, Tabs } from "antd";
import AnnouncementsPanel from "../../features/stock-insights/AnnouncementsPanel";
import FundFlowPanel from "../../features/stock-insights/FundFlowPanel";
import ResearchReportsPanel from "../../features/stock-insights/ResearchReportsPanel";
import { useStyles } from "../../styles/ui";
import StockNewsPanel from "./StockNewsPanel";
import StockSectionTitle from "./StockSectionTitle";

type InformationTab = "bulletins" | "reports" | "fund-flow" | "news";

function ActivePanel({ activeKey, code }: { activeKey: InformationTab; code: string }) {
  switch (activeKey) {
    case "reports":
      return <ResearchReportsPanel code={code} />;
    case "fund-flow":
      return <FundFlowPanel code={code} />;
    case "news":
      return <StockNewsPanel code={code} />;
    case "bulletins":
    default:
      return <AnnouncementsPanel code={code} />;
  }
}

export default function StockInformationTabs({ code }: { code: string }) {
  const [activeKey, setActiveKey] = useState<InformationTab>("bulletins");
  const { cardStyle } = useStyles();
  const tabs = [
    { key: "bulletins", label: <span className="stock-information-tab"><span aria-hidden="true"><FileTextOutlined /></span>公司公告</span> },
    { key: "reports", label: <span className="stock-information-tab"><span aria-hidden="true"><ReadOutlined /></span>券商研报</span> },
    { key: "fund-flow", label: <span className="stock-information-tab"><span aria-hidden="true"><LineChartOutlined /></span>资金流向</span> },
    { key: "news", label: <span className="stock-information-tab"><span aria-hidden="true"><GlobalOutlined /></span>相关新闻</span> },
  ];

  return (
    <Card
      className="stock-section-card stock-information-card"
      title={<StockSectionTitle icon={<ReadOutlined />} title="资讯与研究" description="公告、机构观点与市场动态" />}
      style={cardStyle}
      styles={{ body: { paddingTop: 0 } }}
    >
      <Tabs
        activeKey={activeKey}
        onChange={(key) => setActiveKey(key as InformationTab)}
        items={tabs.map((tab) => ({
          ...tab,
          children: tab.key === activeKey ? <ActivePanel activeKey={activeKey} code={code} /> : null,
        }))}
      />
    </Card>
  );
}
