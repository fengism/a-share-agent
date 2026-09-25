import { useState } from "react";
import { CommentOutlined, FileTextOutlined, GlobalOutlined, ReadOutlined } from "@ant-design/icons";
import { Card, Tabs } from "antd";
import AnnouncementsPanel from "../../features/stock-insights/AnnouncementsPanel";
import ResearchReportsPanel from "../../features/stock-insights/ResearchReportsPanel";
import { useStyles } from "../../styles/ui";
import StockRetailCommentsPanel from "./StockRetailCommentsPanel";
import StockNewsPanel from "./StockNewsPanel";
import StockSectionTitle from "./StockSectionTitle";

type InformationTab = "bulletins" | "reports" | "news" | "comments";

function ActivePanel({ activeKey, code }: { activeKey: InformationTab; code: string }) {
  switch (activeKey) {
    case "comments":
      return <StockRetailCommentsPanel code={code} />;
    case "reports":
      return <ResearchReportsPanel code={code} />;
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
    { key: "news", label: <span className="stock-information-tab"><span aria-hidden="true"><GlobalOutlined /></span>相关新闻</span> },
    { key: "comments", label: <span className="stock-information-tab"><span aria-hidden="true"><CommentOutlined /></span>散户评论</span> },
  ];

  return (
    <Card
      className="stock-section-card stock-information-card"
      title={<StockSectionTitle icon={<ReadOutlined />} title="资讯与研究" description="公告、机构观点、市场动态与散户讨论" />}
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
