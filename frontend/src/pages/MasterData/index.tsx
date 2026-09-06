import { lazy, Suspense } from "react";
import { Tabs, Typography } from "antd";
import { AppstoreOutlined, DatabaseOutlined, IdcardOutlined } from "@ant-design/icons";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import { useStyles } from "../../styles/ui";
import RouteLoadingFallback from "../../components/RouteLoadingFallback";

const StockProfile = lazy(() => import("../../features/master-data/StockProfileTab"));
const StockConcept = lazy(() => import("../../features/master-data/StockConceptTab"));
const IndustryClassification = lazy(() => import("../../features/master-data/IndustryClassificationTab"));

const { Title, Paragraph } = Typography;

const TAB_KEYS = ["profile", "concept", "industry"] as const;
type MasterDataTab = (typeof TAB_KEYS)[number];

export default function MasterDataPage() {
  const { pageContainerStyle, pageDescriptionStyle, pageTitleStyle } = useStyles();
  const [activeTab, setActiveTab] = useUrlSearchParam<MasterDataTab>("tab", "profile", {
    allowedValues: TAB_KEYS,
  });

  const tabItems = [
    {
      key: "profile",
      label: (
        <span>
          <IdcardOutlined /> 个股基础资料
        </span>
      ),
      children: (
        <Suspense fallback={<RouteLoadingFallback />}>
          <StockProfile />
        </Suspense>
      ),
    },
    {
      key: "concept",
      label: (
        <span>
          <AppstoreOutlined /> 概念基础数据
        </span>
      ),
      children: (
        <Suspense fallback={<RouteLoadingFallback />}>
          <StockConcept />
        </Suspense>
      ),
    },
    {
      key: "industry",
      label: (
        <span>
          <DatabaseOutlined /> 行业基础数据
        </span>
      ),
      children: (
        <Suspense fallback={<RouteLoadingFallback />}>
          <IndustryClassification />
        </Suspense>
      ),
    },
  ];

  return (
    <div style={pageContainerStyle} className="master-data-page">
      <header style={{ marginBottom: 12 }}>
        <div className="u-page-title u-page-title--compact">
          <Title level={3} style={pageTitleStyle}>
            <DatabaseOutlined /> 基础数据管理
          </Title>
        </div>
        <Paragraph style={pageDescriptionStyle}>
          统一管理全市场股票的个股基础资料（代码名称、上市市场与时间、核心主营业务等）、概念标签与申万行业分类，支持全量同步、智能补充与手工维护。
        </Paragraph>
      </header>

      <Tabs
        activeKey={activeTab}
        onChange={(k) => setActiveTab(k as MasterDataTab)}
        items={tabItems}
        size="middle"
        destroyInactiveTabPane={false}
      />
    </div>
  );
}
