import { LineChartOutlined } from "@ant-design/icons";
import { Card, Tabs } from "antd";
import FundFlowPanel from "../../features/stock-insights/FundFlowPanel";
import { useStyles } from "../../styles/ui";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import StockFinancialMetrics from "./StockFinancialMetrics";
import StockInformationTabs from "./StockInformationTabs";
import StockValuationTab from "./StockValuationTab";
import StockSectionTitle from "./StockSectionTitle";

const DETAIL_TABS = ["financial", "valuation", "fund-flow", "information"] as const;

export default function StockDetailTabs({ code }: { code: string }) {
  const { cardStyle } = useStyles();
  const [activeKey, setActiveKey] = useUrlSearchParam("tab", "financial", { allowedValues: DETAIL_TABS });
  return (
    <section className="stock-detail-tabs" aria-label="个股资料详情">
      <Tabs
        activeKey={activeKey}
        onChange={setActiveKey}
        items={[
          { key: "financial", label: "财务", children: activeKey === "financial" ? <StockFinancialMetrics code={code} /> : null },
          { key: "valuation", label: "估值", children: activeKey === "valuation" ? <StockValuationTab code={code} /> : null },
          {
            key: "fund-flow",
            label: "资金流向",
            children: activeKey === "fund-flow" ? (
              <Card
                className="stock-section-card stock-fund-flow-card"
                title={<StockSectionTitle icon={<LineChartOutlined />} title="资金流向" description="主力与各类订单净流入 · 近60日走势" />}
                style={cardStyle}
              >
                <FundFlowPanel code={code} />
              </Card>
            ) : null,
          },
          { key: "information", label: "资讯", children: activeKey === "information" ? <StockInformationTabs code={code} /> : null },
        ]}
      />
    </section>
  );
}
