import { BarChartOutlined } from "@ant-design/icons";
import { Card } from "antd";
import { useAnalysisSnapshot } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import FinancialDataSections from "../../features/investment-research/FinancialDataSections";
import FundamentalSummary from "../../features/investment-research/FundamentalSummary";
import { useStyles } from "../../styles/ui";
import StockSectionTitle from "./StockSectionTitle";

export default function StockFinancialMetrics({ code }: { code: string }) {
  const { cardStyle } = useStyles();
  const analysisQuery = useAnalysisSnapshot(code);

  return (
    <Card
      className="stock-section-card stock-financial-card"
      title={(
        <StockSectionTitle
          icon={<BarChartOutlined />}
          title="财务指标"
          description="基本面研判、营收构成与最近四个报告期财务指标"
        />
      )}
      style={cardStyle}
    >
      <div className="stock-financial-content">
        <SectionDataState
          isLoading={analysisQuery.isLoading}
          error={analysisQuery.error}
          onRetry={() => analysisQuery.refetch()}
          errorTitle="基本面摘要加载失败"
          minHeight={160}
        >
          <FundamentalSummary fundamental={analysisQuery.data?.cached_analysis?.fundamental} />
        </SectionDataState>
        <FinancialDataSections code={code} />
      </div>
    </Card>
  );
}
