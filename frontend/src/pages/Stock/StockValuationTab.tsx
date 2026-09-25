import { lazy, Suspense } from "react";
import { Alert, Card, Skeleton } from "antd";
import { LineChartOutlined } from "@ant-design/icons";
import { useSearchParams } from "react-router-dom";
import { formatAnalysisDate, normalizeAnalysisDate } from "../../features/investment-research/analysisHistoryUrl";
import { useStyles } from "../../styles/ui";
import StockSectionTitle from "./StockSectionTitle";

const ValuationPanel = lazy(() => import("../../features/investment-research/ValuationPanel"));

export default function StockValuationTab({ code }: { code: string }) {
  const [searchParams] = useSearchParams();
  const date = normalizeAnalysisDate(searchParams.get("date"));
  const { cardStyle } = useStyles();

  return (
    <Card
      className="stock-section-card stock-valuation-card stock-research-report"
      title={<StockSectionTitle icon={<LineChartOutlined />} title="估值分析" description="估值方法、DCF 情景、机构预期与同行对比" />}
      style={cardStyle}
    >
      <div style={{ display: "grid", gap: 16, minWidth: 0 }}>
        {date ? <Alert type="info" title={`来自 ${formatAnalysisDate(date)} 的历史报告；以下估值为最新可用数据，并非历史快照`} /> : null}
        <Suspense fallback={<div aria-label="估值面板加载中"><Skeleton active paragraph={{ rows: 7 }} /></div>}>
          <ValuationPanel code={code} />
        </Suspense>
      </div>
    </Card>
  );
}
