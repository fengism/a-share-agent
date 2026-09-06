import { BarChartOutlined } from "@ant-design/icons";
import { Card } from "antd";
import KeyFinancialMetricsSection from "../../features/investment-research/KeyFinancialMetricsSection";
import { useStyles } from "../../styles/ui";
import StockSectionTitle from "./StockSectionTitle";

export default function StockFinancialMetrics({ code }: { code: string }) {
  const { cardStyle } = useStyles();

  return (
    <Card
      className="stock-section-card stock-financial-card"
      title={(
        <StockSectionTitle
          icon={<BarChartOutlined />}
          title="财务指标"
          description="盈利、资产与现金质量 · 最近四个报告期"
        />
      )}
      style={cardStyle}
    >
      <KeyFinancialMetricsSection code={code} showHeader={false} />
    </Card>
  );
}
