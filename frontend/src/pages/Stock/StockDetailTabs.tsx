import { BarChartOutlined, LineChartOutlined } from "@ant-design/icons";
import { Card, Tabs } from "antd";
import KeyFinancialMetricsSection from "../../features/investment-research/KeyFinancialMetricsSection";
import RevenueBreakdownSection from "../../features/investment-research/RevenueBreakdownSection";
import FundFlowPanel from "../../features/stock-insights/FundFlowPanel";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import { useStyles } from "../../styles/ui";
import HKIndustryComparisonSection from "./HKIndustryComparisonSection";
import StockFinancialMetrics from "./StockFinancialMetrics";
import StockInformationTabs from "./StockInformationTabs";
import StockSectionTitle from "./StockSectionTitle";
import StockValuationTab from "./StockValuationTab";

const DETAIL_TABS = ["financial", "valuation", "fund-flow", "information"] as const;

export default function StockDetailTabs({ code, market = "cn" }: { code: string; market?: "cn" | "hk" }) {
  const { cardStyle } = useStyles();
  const [activeKey, setActiveKey] = useUrlSearchParam("tab", "financial", { allowedValues: DETAIL_TABS });

  if (market === "hk") {
    return (
      <section className="stock-detail-tabs" aria-label="个股资料详情">
        <Tabs
          activeKey={activeKey}
          onChange={setActiveKey}
          items={[
            {
              key: "financial",
              label: "财务",
              forceRender: true,
              children: (
                <>
                  <RevenueBreakdownSection code={code} />
                  <Card
                    data-testid="hk-financial-data"
                    className="stock-section-card stock-financial-card"
                    title={(
                      <StockSectionTitle
                        icon={<BarChartOutlined />}
                        title="财务数据"
                        description="同花顺 F10 · 最近四个报告期 · 金额按公司原始披露币种"
                      />
                    )}
                    style={cardStyle}
                  >
                    <KeyFinancialMetricsSection code={code} showHeader={false} />
                  </Card>
                </>
              ),
            },
            {
              key: "valuation",
              label: "行业对比",
              forceRender: true,
              children: <HKIndustryComparisonSection code={code} />,
            },
            {
              key: "information",
              label: "资讯",
              children: activeKey === "information" ? <StockInformationTabs code={code} /> : null,
            },
          ]}
        />
      </section>
    );
  }

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
